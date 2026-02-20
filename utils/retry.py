# utils/retry.py
import time
import random
import functools
import anthropic
from utils.logger import get_logger

logger = get_logger("retry")


def retry_on_rate_limit(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """
    Decorator that retries a function on Anthropic API rate limit or overload errors.
    Uses exponential backoff with jitter.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APITimeoutError) as e:
                    last_exc = e
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    logger.warning(
                        f"API error on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
