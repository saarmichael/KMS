import time

import pytest

from kms.ai.errors import ErrorVerdict, RetryPolicy, call_with_retries

POLICY = RetryPolicy(
    max_attempts=4, first_wait_seconds=1.0, max_server_wait_seconds=60.0, timeout_seconds=120.0
)


class StubError(Exception):
    """An error whose verdict the test decides."""

    def __init__(self, retryable: bool, server_wait_seconds: float | None = None):
        super().__init__("from the test")
        self.verdict = ErrorVerdict(retryable=retryable, server_wait_seconds=server_wait_seconds)


def classify_stub(error: Exception) -> ErrorVerdict:
    return error.verdict


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


def test_retries_a_retryable_error_then_succeeds(sleeps):
    call = FailingCall([StubError(retryable=True), StubError(retryable=True)])

    assert call_with_retries(call, "test", classify_stub, POLICY) == "answer"
    assert call.calls == 3
    # About 1 then 4 seconds, each with up to one first wait of jitter.
    assert 1 <= sleeps[0] <= 2
    assert 4 <= sleeps[1] <= 5


def test_not_retryable_error_is_raised_at_once(sleeps):
    error = StubError(retryable=False)
    call = FailingCall([error])

    with pytest.raises(StubError) as raised:
        call_with_retries(call, "test", classify_stub, POLICY)
    assert raised.value is error
    assert call.calls == 1
    assert sleeps == []


def test_gives_up_after_the_policy_attempts(sleeps):
    errors = [StubError(retryable=True) for _ in range(5)]
    last_error = errors[3]
    call = FailingCall(errors)

    with pytest.raises(StubError) as raised:
        call_with_retries(call, "test", classify_stub, POLICY)
    assert raised.value is last_error
    assert call.calls == 4


def test_waits_as_long_as_the_server_asks(sleeps):
    call = FailingCall([StubError(retryable=True, server_wait_seconds=7.0)])

    assert call_with_retries(call, "test", classify_stub, POLICY) == "answer"
    assert sleeps == [7.0]


def test_server_wait_over_the_policy_cap_is_raised_at_once(sleeps):
    error = StubError(retryable=True, server_wait_seconds=3600.0)
    call = FailingCall([error])

    with pytest.raises(StubError) as raised:
        call_with_retries(call, "test", classify_stub, POLICY)
    assert raised.value is error
    assert call.calls == 1
    assert sleeps == []


def test_one_attempt_policy_never_retries(sleeps):
    one_attempt = RetryPolicy(
        max_attempts=1, first_wait_seconds=0.0, max_server_wait_seconds=0.0, timeout_seconds=3.0
    )
    error = StubError(retryable=True)
    call = FailingCall([error])

    with pytest.raises(StubError) as raised:
        call_with_retries(call, "test", classify_stub, one_attempt)
    assert raised.value is error
    assert call.calls == 1
    assert sleeps == []
