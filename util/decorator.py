import time
from functools import wraps
from typing import Callable, Any

from loguru import logger


def retry(retries: int = 3, delay: float = 1) -> Callable:
    """
    A decorator that retries a function execution a specified number of times with a delay between retries.

    Args:
        retries (int): The number of times to retry the function. Must be greater than 0.
        delay (float): The delay in seconds between retries. Must be greater than 0.

    Returns:
        Callable: A decorator that wraps the function with retry logic.
    """
    if retries < 1 or delay <= 0:
        raise ValueError('Wrong param')

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for i in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == retries:
                        logger.error(f'Error: {repr(e)}.')
                        logger.error(f'"{func.__name__}()" failed after {retries} retries.')
                        break
                    else:
                        logger.debug(f'Error: {repr(e)} -> Retrying...')
                        time.sleep(delay)

        return wrapper

    return decorator
