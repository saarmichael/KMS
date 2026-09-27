"""What to do when a vendor call fails: wait and try again, move to the next model, or give up.

`classify` sorts every error into one of three kinds, and `call_with_retries` runs one call,
retrying it while the error is worth retrying. The vendor SDKs' own retries stay off, so this is
the only place that decides how long to wait and how often to try.
"""

import logging
from collections.abc import Callable
from enum import StrEnum
from http import HTTPStatus

import httpx
import tenacity
from google.genai import errors as gemini_errors
from voyageai import error as voyage_errors

logger = logging.getLogger(__name__)


class ErrorKind(StrEnum):
    """What the caller should do about a failed vendor call.

    A StrEnum, so each kind prints as its plain value in the log.
    """

    TRANSIENT = "transient"
    OVERLOADED = "overloaded"
    PERMANENT = "permanent"


# One try and three retries: the waits add up to about 21 seconds, long enough to ride out a
# short outage without holding a worker on a vendor that is really down.
MAX_CALL_ATTEMPTS = 4
# A server that asks for a longer pause has run out of quota for a while; waiting would only
# hold the worker, so the error is raised at once.
MAX_SERVER_WAIT_SECONDS = 60


def classify(error: Exception) -> ErrorKind:
    """Sort a vendor error by what the caller should do about it.

    Args:
        error: Whatever the vendor call raised.

    Returns:
        OVERLOADED when another model may answer now, TRANSIENT when the same call may work
        after a wait, PERMANENT when trying again cannot help. Never raises.
    """
    if isinstance(error, gemini_errors.APIError):
        # Every Gemini quota is per model, so a model out of quota does not stop the next one.
        if error.code in (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE):
            return ErrorKind.OVERLOADED
        if error.code in (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.GATEWAY_TIMEOUT,
        ):
            return ErrorKind.TRANSIENT
        return ErrorKind.PERMANENT
    # The Gemini SDK lets timeouts and dropped connections through as raw httpx errors.
    if isinstance(error, httpx.TransportError):
        return ErrorKind.TRANSIENT
    if isinstance(error, voyage_errors.VoyageError):
        transient_errors = (
            voyage_errors.RateLimitError,
            voyage_errors.ServerError,
            voyage_errors.ServiceUnavailableError,
            voyage_errors.Timeout,
            voyage_errors.APIConnectionError,
            voyage_errors.TryAgain,
        )
        if isinstance(error, transient_errors):
            return ErrorKind.TRANSIENT
        status = error.http_status
        if status is not None and (
            status == HTTPStatus.TOO_MANY_REQUESTS or status >= HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            return ErrorKind.TRANSIENT
        return ErrorKind.PERMANENT
    return ErrorKind.PERMANENT


def server_retry_delay(error: Exception) -> float | None:
    """Read how long Gemini asked us to wait before trying again.

    Gemini puts the wait in a RetryInfo entry of the error body, as a string like "33s".

    Args:
        error: Whatever the vendor call raised.

    Returns:
        The wait in seconds, or None when the error is not from Gemini, has no RetryInfo, or its
        body is not in the expected shape. Never raises.
    """
    if not isinstance(error, gemini_errors.APIError):
        return None
    try:
        for detail in error.details["error"]["details"]:
            if detail["@type"] == "type.googleapis.com/google.rpc.RetryInfo":
                return float(detail["retryDelay"].removesuffix("s"))
    except (KeyError, TypeError, AttributeError, ValueError):
        return None
    return None


def call_with_retries[T](call: Callable[[], T], description: str) -> T:
    """Run one vendor call, waiting and trying again while the error is worth retrying.

    A permanent error is raised at once. Any other error is retried, up to MAX_CALL_ATTEMPTS
    calls in all. The wait is the one the server asked for when it asked; otherwise about 1, 4
    and 16 seconds, plus up to a second of jitter so that workers do not retry in step.

    Args:
        call: The vendor call, with its arguments already bound.
        description: What the call is, for the log.

    Returns:
        What `call` returned.

    Raises:
        Exception: The error `call` raised, unchanged, when it is permanent, when the server asks
            for a wait over MAX_SERVER_WAIT_SECONDS, or when the last attempt fails.
    """
    backoff = tenacity.wait_exponential(multiplier=1, exp_base=4) + tenacity.wait_random(0, 1)

    def should_retry(error: BaseException) -> bool:
        """Retry an error that is not permanent, unless the server asks for too long a wait.

        Args:
            error: The error the last attempt raised.

        Returns:
            True to wait and call again, False to raise the error.
        """
        if not isinstance(error, Exception) or classify(error) == ErrorKind.PERMANENT:
            return False
        delay = server_retry_delay(error)
        return delay is None or delay <= MAX_SERVER_WAIT_SECONDS

    def wait_seconds(retry_state: tenacity.RetryCallState) -> float:
        """Choose the wait before the next attempt.

        Args:
            retry_state: Tenacity's record of the attempts so far.

        Returns:
            The server's wait when it gave one, otherwise the backoff with jitter.
        """
        delay = server_retry_delay(retry_state.outcome.exception())
        if delay is not None:
            return delay
        return backoff(retry_state)

    def log_retry(retry_state: tenacity.RetryCallState) -> None:
        """Log the failed attempt and the wait before the next one.

        Args:
            retry_state: Tenacity's record of the attempts so far.
        """
        error = retry_state.outcome.exception()
        logger.warning(
            "vendor_retry call=%s attempt=%d kind=%s wait_s=%.1f error=%r",
            description,
            retry_state.attempt_number,
            classify(error),
            retry_state.next_action.sleep,
            error,
        )

    retrying = tenacity.Retrying(
        retry=tenacity.retry_if_exception(should_retry),
        wait=wait_seconds,
        stop=tenacity.stop_after_attempt(MAX_CALL_ATTEMPTS),
        before_sleep=log_retry,
        reraise=True,
    )
    return retrying(call)
