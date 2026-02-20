# tests/utils/test_retry.py
import sys
sys.path.insert(0, '.')
from unittest.mock import MagicMock
import anthropic
from utils.retry import retry_on_rate_limit


def test_succeeds_on_first_try():
    call_count = [0]

    @retry_on_rate_limit(max_retries=3, base_delay=0.01)
    def my_func():
        call_count[0] += 1
        return "success"

    assert my_func() == "success"
    assert call_count[0] == 1


def test_retries_on_rate_limit_error():
    call_count = [0]

    @retry_on_rate_limit(max_retries=3, base_delay=0.01)
    def my_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise anthropic.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429, headers={}),
                body={}
            )
        return "success"

    assert my_func() == "success"
    assert call_count[0] == 3


def test_raises_after_max_retries():
    call_count = [0]

    @retry_on_rate_limit(max_retries=2, base_delay=0.01)
    def my_func():
        call_count[0] += 1
        raise anthropic.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429, headers={}),
            body={}
        )

    try:
        my_func()
        assert False, "Should have raised"
    except anthropic.RateLimitError:
        pass
    assert call_count[0] == 3  # 1 initial + 2 retries
