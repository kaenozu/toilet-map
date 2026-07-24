"""Job retry policy tests."""

from app.job_queue import retry_delay_seconds


def test_retry_delay_is_exponential_and_capped() -> None:
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(4) == 16
    assert retry_delay_seconds(20) == 300
