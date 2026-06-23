from collections.abc import Callable
from functools import wraps
from typing import Any


def _pass_through_decorator(*decorator_args: Any, **decorator_kwargs: Any) -> Callable:
    """Returnerer en no-op decorator og tolererer både @decorator og @decorator(...)."""

    if (
        decorator_args
        and callable(decorator_args[0])
        and len(decorator_args) == 1
        and not decorator_kwargs
    ):
        func = decorator_args[0]

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any):
            return func(*args, **kwargs)

        return wrapped

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any):
            return func(*args, **kwargs)

        return wrapped

    return decorator


def auth_required(*args: Any, **kwargs: Any) -> Callable:
    return _pass_through_decorator(*args, **kwargs)


def auth_required_site(*args: Any, **kwargs: Any) -> Callable:
    return _pass_through_decorator(*args, **kwargs)
