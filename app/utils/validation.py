from typing import Iterable


def has_required_fields(data: dict, required: Iterable[str]) -> bool:
    """Return True if all required fields are present in the given dict."""
    if not isinstance(data, dict):
        return False
    return all(field in data for field in required)
