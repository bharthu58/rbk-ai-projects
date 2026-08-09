import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_ATTEMPTS = 3
_BACKOFF_SECONDS = (2, 4)


def retry(
    fn: Callable[[], T],
    *,
    attempts: int = _ATTEMPTS,
    backoff: tuple[float, ...] = _BACKOFF_SECONDS,
    retryable: tuple[type[BaseException], ...] = (OSError, TimeoutError, ConnectionError),
) -> T:
    """Retry fn() a small, fixed number of times on network-level errors only.

    Deliberately narrow: auth failures, HTTP 4xx/5xx, and other permanent errors
    are not in `retryable` by default and propagate immediately — retrying those
    just delays a failure that a scheduled re-run five-to-fifteen minutes later
    (DESIGN.md's catch-up behavior) won't fix any faster.
    """
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except retryable as exc:
            last_exc = exc
            if attempt < attempts - 1:
                delay = backoff[min(attempt, len(backoff) - 1)]
                logger.warning(
                    "transient error (%s), retrying in %ss (attempt %d/%d)",
                    exc, delay, attempt + 1, attempts,
                )
                time.sleep(delay)
    assert last_exc is not None
    raise last_exc
