import re


def normalize_phone(phone: str) -> str:
    """Normalize a 10-digit phone number to +91XXXXXXXXXX format.

    Non-digit characters are stripped. Raises ValueError if the
    resulting string is not exactly 10 digits long.
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) != 10:
        raise ValueError("phone must be 10 digits")
    return f"+91{digits}"


__all__ = ["normalize_phone"]
