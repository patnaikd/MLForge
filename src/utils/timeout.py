"""Timeout management utilities."""

import asyncio
from typing import TypeVar

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass


class ActivityTimeoutError(TimeoutError):
    """Raised when there's no activity for too long."""

    pass


class OverallTimeoutError(TimeoutError):
    """Raised when overall execution time is exceeded."""

    pass


async def run_with_timeout(
    coro: asyncio.coroutines,
    timeout: float,
    error_class: type[TimeoutError] = TimeoutError,
) -> T:
    """Run a coroutine with a timeout.

    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        error_class: Exception class to raise on timeout

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If the operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise error_class(f"Operation timed out after {timeout} seconds")
