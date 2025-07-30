# Logging Policy

This project uses JSON formatted logs with a global masking filter.
Sensitive fields such as passwords, OTP codes, tokens and email addresses are removed
from logs unless DEBUG level logging is enabled in a non-production environment.

## Examples

```python
logger.info({"email": "user@example.com", "otp": "123456"})
# -> {"email": "[REDACTED]", "otp": "[REDACTED]", ...}

logger.debug({"password": "secret"})  # in development
# -> {"password": "secret", ...}
```

Ensure any structured data passed to loggers uses dictionaries so the masking
filter can properly sanitize values.
