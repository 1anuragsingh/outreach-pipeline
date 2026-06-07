import functools
import time

from utils.logger import logger


def retry(max_attempts: int = 3, delay: float = 2, backoff: float = 2):
    """Exponential-backoff retry decorator.

    max_attempts: total number of attempts (1 original + max_attempts-1 retries).
    delay:        seconds to wait before the first retry.
    backoff:      multiplier applied to the wait on each successive retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = delay
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        logger.warning(
                            "Retry attempt %d/%d for %s — %s",
                            attempt, max_attempts, func.__name__, exc,
                        )
                        time.sleep(wait)
                        wait *= backoff
            raise last_exc
        return wrapper
    return decorator


def rate_limit(seconds: float) -> None:
    """Sleep for `seconds`, logging the wait so it shows up in the run trace."""
    logger.info("Rate limiting: waiting %ss", seconds)
    time.sleep(seconds)
