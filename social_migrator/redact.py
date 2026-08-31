import re

_SECRET = re.compile(r"(?i)(sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,})")


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _SECRET.sub("[REDACTED]", value)
    return value
