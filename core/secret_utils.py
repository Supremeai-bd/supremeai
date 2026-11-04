"""Small helpers for passing secret settings to APIs that require plain strings."""

from typing import Any


def unwrap_secret(value: Any) -> Any:
    """Return a Pydantic SecretStr's value, leaving ordinary values unchanged.

    Call only at the boundary of an SDK or driver that needs a raw string. Never
    log the returned value.
    """
    get_secret_value = getattr(value, "get_secret_value", None)
    return get_secret_value() if callable(get_secret_value) else value
