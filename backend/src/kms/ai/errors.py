"""How hard to try a vendor call again when it fails.

Each caller picks a `RetryPolicy`, because how long a call may take depends on who waits for it: the
worker can ride out an outage, a search cannot keep its user waiting. Each vendor adapter says what
its own errors mean, as an `ErrorVerdict`. `call_with_retries` puts the two together, and knows
nothing about any vendor. The vendor SDKs' own retries stay off, so this is the only place that
decides how long to wait and how often to try.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import tenacity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try one vendor call.

    Attributes:
        max_attempts: The most calls in all, the first one included; 1 never retries.
        first_wait_seconds: The wait before the first retry; each later wait is four times the
            one before, plus up to this much again of random jitter so that callers do not retry
            in step.
        max_server_wait_seconds: The longest wait honoured when the vendor asks for one; a
            longer ask means the quota is out for a while, and the error is raised at once.
        timeout_seconds: How long one request may take before it counts as lost.
    """

    max_attempts: int
    first_wait_seconds: float
    max_server_wait_seconds: float
    timeout_seconds: float


@dataclass(frozen=True)
class ErrorVerdict:
    """What a vendor adapter makes of one of its errors.

    Attributes:
        retryable: True when the same call may work after a wait.
        server_wait_seconds: How long the vendor asked us to wait, or None when it did not say.
    """

    retryable: bool
    server_wait_seconds: float | None


# The worker and the command line: no one is waiting, so a short outage is ridden out. The waits
# of about 1, 4 and 16 seconds add up to about 21; a large image on a slow model may take two
# minutes.
BACKGROUND_POLICY = RetryPolicy(
    max_attempts=4, first_wait_seconds=1.0, max_server_wait_seconds=60.0, timeout_seconds=120.0
)
# A call a search cannot do without: one quick retry covers a dropped connection or a brief rate
# limit, and the timeout cuts a lost call long before the user gives up.
INTERACTIVE_POLICY = RetryPolicy(
    max_attempts=2, first_wait_seconds=0.5, max_server_wait_seconds=1.0, timeout_seconds=5.0
)
# A call that only adds to results the user already has: never retried, since losing it costs
# less than a wait.
OPTIONAL_POLICY = RetryPolicy(
    max_attempts=1, first_wait_seconds=0.0, max_server_wait_seconds=0.0, timeout_seconds=3.0
)


def call_with_retries[T](
    call: Callable[[], T],
    description: str,
    classify: Callable[[Exception], ErrorVerdict],
    policy: RetryPolicy,
) -> T:
    """Run one vendor call, waiting and trying again while the error is worth retrying.

    Args:
        call: The vendor call, with its arguments already bound.
        description: What the call is, for the log.
        classify: The vendor's reading of its own errors.
        policy: How hard to try.

    Returns:
        What `call` returned.

    Raises:
        Exception: The error `call` raised, unchanged, when it is not retryable, when the vendor
            asks for a wait over the policy's `max_server_wait_seconds`, or when the last
            attempt fails.
    """
    backoff = tenacity.wait_exponential(
        multiplier=policy.first_wait_seconds, exp_base=4
    ) + tenacity.wait_random(0, policy.first_wait_seconds)

    def should_retry(error: BaseException) -> bool:
        """Retry an error the vendor calls retryable, unless it asks for too long a wait.

        Args:
            error: The error the last attempt raised.

        Returns:
            True to wait and call again, False to raise the error.
        """
        if not isinstance(error, Exception):
            return False
        verdict = classify(error)
        if not verdict.retryable:
            return False
        if verdict.server_wait_seconds is None:
            return True
        return verdict.server_wait_seconds <= policy.max_server_wait_seconds

    def wait_seconds(retry_state: tenacity.RetryCallState) -> float:
        """Choose the wait before the next attempt.

        Args:
            retry_state: Tenacity's record of the attempts so far.

        Returns:
            The vendor's wait when it gave one, otherwise the backoff with jitter.
        """
        verdict = classify(retry_state.outcome.exception())
        if verdict.server_wait_seconds is not None:
            return verdict.server_wait_seconds
        return backoff(retry_state)

    def log_retry(retry_state: tenacity.RetryCallState) -> None:
        """Log the failed attempt and the wait before the next one.

        Args:
            retry_state: Tenacity's record of the attempts so far.
        """
        logger.warning(
            "vendor_retry call=%s attempt=%d wait_s=%.1f error=%r",
            description,
            retry_state.attempt_number,
            retry_state.next_action.sleep,
            retry_state.outcome.exception(),
        )

    retrying = tenacity.Retrying(
        retry=tenacity.retry_if_exception(should_retry),
        wait=wait_seconds,
        stop=tenacity.stop_after_attempt(policy.max_attempts),
        before_sleep=log_retry,
        reraise=True,
    )
    return retrying(call)
