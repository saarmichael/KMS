import time

import httpx
import pytest
from google.genai.errors import ClientError, ServerError
from pydantic import BaseModel, ValidationError
from voyageai import error as voyage_errors

from kms.ai.errors import ErrorKind, call_with_retries, classify, server_retry_delay


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


@pytest.fixture
def sleeps(monkeypatch):
    # Tenacity sleeps through time.sleep; recording instead keeps the tests instant.
    requested = []
    monkeypatch.setattr(time, "sleep", requested.append)
    return requested


class FailingCall:
    def __init__(self, errors: list[Exception]):
        self.errors = errors
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "answer"


@pytest.mark.parametrize(("code", "status"), [(429, "RESOURCE_EXHAUSTED"), (503, "UNAVAILABLE")])
def test_gemini_429_and_503_are_overloaded(code, status):
    assert classify(gemini_error(code, status)) == ErrorKind.OVERLOADED


@pytest.mark.parametrize("code", [500, 502, 504])
def test_gemini_500_502_504_are_transient(code):
    assert classify(gemini_error(code, "INTERNAL")) == ErrorKind.TRANSIENT


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
def test_gemini_client_errors_are_permanent(error):
    assert classify(error) == ErrorKind.PERMANENT


@pytest.mark.parametrize(
    "error",
    [
        voyage_errors.RateLimitError("slow down", http_status=429),
        voyage_errors.ServerError("broken", http_status=500),
        voyage_errors.APIError("bad gateway", http_status=502),
        voyage_errors.Timeout("timed out"),
        voyage_errors.APIConnectionError("no connection"),
    ],
)
def test_voyage_rate_limit_server_and_network_errors_are_transient(error):
    assert classify(error) == ErrorKind.TRANSIENT


@pytest.mark.parametrize(
    "error",
    [
        voyage_errors.AuthenticationError("bad key", http_status=401),
        voyage_errors.InvalidRequestError("bad input", http_status=400),
        voyage_errors.MalformedRequestError("unreadable", http_status=422),
    ],
)
def test_voyage_auth_and_bad_request_are_permanent(error):
    assert classify(error) == ErrorKind.PERMANENT


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("refused"), httpx.ReadTimeout("no answer in time")]
)
def test_network_errors_are_transient(error):
    assert classify(error) == ErrorKind.TRANSIENT


def test_unknown_error_is_permanent():
    class Answer(BaseModel):
        title: str

    with pytest.raises(ValidationError) as validation:
        Answer.model_validate({})
    assert classify(validation.value) == ErrorKind.PERMANENT
    assert classify(ValueError("unexpected")) == ErrorKind.PERMANENT


def test_server_retry_delay_is_read_from_retry_info():
    assert server_retry_delay(gemini_error(429, "RESOURCE_EXHAUSTED", "33s")) == 33.0
    assert server_retry_delay(gemini_error(429, "RESOURCE_EXHAUSTED", "0.5s")) == 0.5
    assert server_retry_delay(gemini_error(429, "RESOURCE_EXHAUSTED")) is None
    assert server_retry_delay(voyage_errors.RateLimitError("slow down", http_status=429)) is None
    assert server_retry_delay(ClientError(429, "not a json object", None)) is None


def test_retries_a_transient_error_then_succeeds(sleeps):
    call = FailingCall([gemini_error(500, "INTERNAL"), gemini_error(500, "INTERNAL")])
    assert call_with_retries(call, "test") == "answer"
    assert call.calls == 3
    assert len(sleeps) == 2
    assert 1 <= sleeps[0] <= 2
    assert 4 <= sleeps[1] <= 5


def test_permanent_error_is_raised_at_once(sleeps):
    error = gemini_error(400, "INVALID_ARGUMENT")
    call = FailingCall([error])
    with pytest.raises(ClientError) as raised:
        call_with_retries(call, "test")
    assert raised.value is error
    assert call.calls == 1
    assert sleeps == []


def test_gives_up_after_four_attempts(sleeps):
    errors = [gemini_error(503, "UNAVAILABLE") for _ in range(5)]
    last_error = errors[3]
    call = FailingCall(errors)
    with pytest.raises(ServerError) as raised:
        call_with_retries(call, "test")
    assert raised.value is last_error
    assert call.calls == 4


def test_waits_as_long_as_the_server_asks(sleeps):
    call = FailingCall([gemini_error(429, "RESOURCE_EXHAUSTED", "7s")])
    assert call_with_retries(call, "test") == "answer"
    assert sleeps == [7.0]


def test_server_wait_over_the_cap_is_raised_at_once(sleeps):
    error = gemini_error(429, "RESOURCE_EXHAUSTED", "3600s")
    call = FailingCall([error])
    with pytest.raises(ClientError) as raised:
        call_with_retries(call, "test")
    assert raised.value is error
    assert call.calls == 1
    assert sleeps == []
