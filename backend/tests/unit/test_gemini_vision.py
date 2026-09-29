import json
import time

import httpx
import pytest
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pydantic import BaseModel, ValidationError

from kms.ai.errors import BACKGROUND_POLICY, RetryPolicy
from kms.ai.gemini import (
    MAX_OUTPUT_TOKENS,
    ContentBlockedError,
    GeminiVision,
    classify_gemini_error,
    is_overloaded,
)
from kms.ai.prompts import TEXT_PROMPT
from kms.ai.schema import Metadata

MODELS = ["first-model", "second-model"]

VALID_ANSWER = json.dumps(
    {
        "title": "Harbour at dusk",
        "description": "Boats moored in a small harbour.",
        "tags": ["boat", "harbour"],
        "visible_text": "",
        "image_type": "photo",
    }
)
# Valid JSON, but the required fields are missing.
INVALID_ANSWER = json.dumps({"title": "Harbour at dusk"})


def gemini_error(code: int, status: str, retry_delay: str | None = None) -> Exception:
    details = []
    if retry_delay is not None:
        details.append(
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}
        )
    body = {
        "error": {"code": code, "message": "from the test", "status": status, "details": details}
    }
    if code >= 500:
        return ServerError(code, body, None)
    return ClientError(code, body, None)


def answer(
    text: str,
    finish_reason: types.FinishReason = types.FinishReason.STOP,
    block_reason: types.BlockedReason | None = None,
) -> types.GenerateContentResponse:
    prompt_feedback = None
    if block_reason is not None:
        prompt_feedback = types.GenerateContentResponsePromptFeedback(block_reason=block_reason)
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
                finish_reason=finish_reason,
            )
        ],
        prompt_feedback=prompt_feedback,
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=50, thoughts_token_count=0
        ),
    )


class StubClient:
    """Stands in for genai.Client: hands out the given answers in order and records each call."""

    def __init__(self, answers: list[types.GenerateContentResponse | Exception]):
        self.models = self
        self.answers = answers
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        next_answer = self.answers.pop(0)
        if isinstance(next_answer, Exception):
            raise next_answer
        return next_answer


@pytest.fixture
def sleeps(monkeypatch):
    # The backoff sleeps through time.sleep; recording instead keeps the tests instant.
    requested = []
    monkeypatch.setattr(time, "sleep", requested.append)
    return requested


def describe_image(client: StubClient):
    return GeminiVision(client, MODELS).describe(
        b"jpeg bytes", "image", "harbour.jpg", None, BACKGROUND_POLICY
    )


def called_models(client: StubClient) -> list[str]:
    return [call["model"] for call in client.calls]


def test_first_model_answers(sleeps):
    client = StubClient([answer(VALID_ANSWER)])
    description = describe_image(client)
    assert description.model == "first-model"
    assert description.metadata == Metadata.model_validate_json(VALID_ANSWER)
    assert called_models(client) == ["first-model"]


@pytest.mark.parametrize(
    "error", [gemini_error(503, "UNAVAILABLE"), gemini_error(429, "RESOURCE_EXHAUSTED")]
)
def test_overloaded_model_moves_to_next_at_once(sleeps, error):
    client = StubClient([error, answer(VALID_ANSWER)])
    description = describe_image(client)
    assert description.model == "second-model"
    assert called_models(client) == ["first-model", "second-model"]
    assert sleeps == []


def test_all_models_overloaded_backs_off_and_restarts_at_first(sleeps):
    client = StubClient(
        [gemini_error(503, "UNAVAILABLE"), gemini_error(503, "UNAVAILABLE"), answer(VALID_ANSWER)]
    )
    description = describe_image(client)
    assert description.model == "first-model"
    assert called_models(client) == ["first-model", "second-model", "first-model"]
    assert len(sleeps) == 1


def test_permanent_error_does_not_try_next_model(sleeps):
    error = gemini_error(402, "PAYMENT_REQUIRED")
    client = StubClient([error])
    with pytest.raises(ClientError) as raised:
        describe_image(client)
    assert raised.value is error
    assert called_models(client) == ["first-model"]
    assert sleeps == []


def test_invalid_answer_is_repaired_once(sleeps):
    client = StubClient([answer(INVALID_ANSWER), answer(VALID_ANSWER)])
    description = describe_image(client)
    assert description.model == "first-model"
    assert called_models(client) == ["first-model", "first-model"]

    # The repair re-sends the request with the image, then the bad answer, then the fix-up ask.
    first_request, bad_answer, repair_request = client.calls[1]["contents"]
    assert first_request == client.calls[0]["contents"][0]
    assert first_request.parts[1].inline_data.data == b"jpeg bytes"
    assert bad_answer.role == "model"
    assert bad_answer.parts[0].text == INVALID_ANSWER
    assert repair_request.role == "user"
    assert "description" in repair_request.parts[0].text


def test_invalid_twice_raises_validation_error(sleeps):
    client = StubClient([answer(INVALID_ANSWER), answer(INVALID_ANSWER)])
    with pytest.raises(ValidationError):
        describe_image(client)
    assert called_models(client) == ["first-model", "first-model"]
    assert sleeps == []


@pytest.mark.parametrize(
    "blocked_answer",
    [
        answer("", block_reason=types.BlockedReason.SAFETY),
        answer("", finish_reason=types.FinishReason.PROHIBITED_CONTENT),
    ],
)
def test_blocked_answer_raises_content_blocked(sleeps, blocked_answer):
    client = StubClient([blocked_answer])
    with pytest.raises(ContentBlockedError, match="Gemini blocked the answer"):
        describe_image(client)
    assert called_models(client) == ["first-model"]
    assert sleeps == []


def test_request_uses_schema_lowest_thinking_and_output_limit(sleeps):
    client = StubClient([answer(VALID_ANSWER)])
    describe_image(client)
    config = client.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is Metadata
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS
    assert config.automatic_function_calling.disable is True


def test_text_file_is_sent_as_text_without_image(sleeps):
    client = StubClient([answer(VALID_ANSWER)])
    vision = GeminiVision(client, MODELS)
    vision.describe("Minutes of the board meeting.", "text", "minutes.txt", None, BACKGROUND_POLICY)
    (request,) = client.calls[0]["contents"]
    assert [part.text for part in request.parts] == [TEXT_PROMPT, "Minutes of the board meeting."]
    assert all(part.inline_data is None for part in request.parts)
    assert "minutes.txt" not in str(request)


def test_request_timeout_follows_the_policy(sleeps):
    client = StubClient([answer(VALID_ANSWER)])
    quick = RetryPolicy(
        max_attempts=1, first_wait_seconds=0.0, max_server_wait_seconds=0.0, timeout_seconds=3.0
    )

    GeminiVision(client, MODELS).describe(b"jpeg bytes", "image", "harbour.jpg", None, quick)

    # The SDK takes the timeout in milliseconds.
    assert client.calls[0]["config"].http_options.timeout == 3000


# --- reading Gemini's errors ---------------------------------------------------


@pytest.mark.parametrize(("code", "status"), [(429, "RESOURCE_EXHAUSTED"), (503, "UNAVAILABLE")])
def test_gemini_429_and_503_are_overloaded_and_retryable(code, status):
    error = gemini_error(code, status)

    assert is_overloaded(error) is True
    assert classify_gemini_error(error).retryable is True


@pytest.mark.parametrize("code", [500, 502, 504])
def test_gemini_500_502_504_are_retryable_but_not_overloaded(code):
    error = gemini_error(code, "INTERNAL")

    assert is_overloaded(error) is False
    assert classify_gemini_error(error).retryable is True


INVALID_API_KEY_BODY = {
    "error": {
        "code": 400,
        "message": "API key not valid.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}
        ],
    }
}


@pytest.mark.parametrize(
    "error",
    [
        ClientError(400, INVALID_API_KEY_BODY, None),
        gemini_error(401, "UNAUTHENTICATED"),
        gemini_error(402, "PAYMENT_REQUIRED"),
        gemini_error(403, "PERMISSION_DENIED"),
        gemini_error(404, "NOT_FOUND"),
        gemini_error(413, "PAYLOAD_TOO_LARGE"),
    ],
)
def test_gemini_client_errors_are_not_retryable(error):
    assert classify_gemini_error(error).retryable is False
    assert is_overloaded(error) is False


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("refused"), httpx.ReadTimeout("no answer in time")]
)
def test_network_errors_are_retryable(error):
    assert classify_gemini_error(error).retryable is True


def test_unknown_error_is_not_retryable():
    class Answer(BaseModel):
        title: str

    with pytest.raises(ValidationError) as validation:
        Answer.model_validate({})
    assert classify_gemini_error(validation.value).retryable is False
    assert classify_gemini_error(ValueError("unexpected")).retryable is False
    assert classify_gemini_error(ContentBlockedError("blocked")).retryable is False


def test_server_wait_is_read_from_retry_info():
    def server_wait(error):
        return classify_gemini_error(error).server_wait_seconds

    assert server_wait(gemini_error(429, "RESOURCE_EXHAUSTED", "33s")) == 33.0
    assert server_wait(gemini_error(429, "RESOURCE_EXHAUSTED", "0.5s")) == 0.5
    assert server_wait(gemini_error(429, "RESOURCE_EXHAUSTED")) is None
    assert server_wait(ClientError(429, "not a json object", None)) is None
