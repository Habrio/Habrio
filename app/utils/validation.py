from typing import Iterable


def has_required_fields(data: dict, required: Iterable[str]) -> bool:
    """Return True if all required fields are present in the given dict."""
    if not isinstance(data, dict):
        return False
    return all(field in data for field in required)

from functools import wraps
from flask import request
from pydantic import ValidationError
from .responses import validation_error_response


def validate_schema(schema):
    """Decorator to validate request JSON against a Pydantic schema."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                obj = schema(**(request.get_json() or {}))
            except ValidationError as ve:
                return validation_error_response(ve.errors())
            request.validated_data = obj
            return fn(*args, **kwargs)
        return wrapper

    return decorator
