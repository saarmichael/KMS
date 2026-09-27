import json
import time

import pytest
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pydantic import ValidationError

from kms.ai.gemini import MAX_OUTPUT_TOKENS, ContentBlockedError, GeminiVision
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


def gemini_error(code: int, status: str) -> Exception:
    body = {"error": {"code": code, "message": "from the test", "status": status}}
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
    return GeminiVision(client, MODELS).describe(b"jpeg bytes", "image", "harbour.jpg", None)


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


def test_text_file_is_sent_as_text_without_image(sleeps):
    client = StubClient([answer(VALID_ANSWER)])
    vision = GeminiVision(client, MODELS)
    vision.describe("Minutes of the board meeting.", "text", "minutes.txt", None)
    (request,) = client.calls[0]["contents"]
    assert [part.text for part in request.parts] == [TEXT_PROMPT, "Minutes of the board meeting."]
    assert all(part.inline_data is None for part in request.parts)
    assert "minutes.txt" not in str(request)
