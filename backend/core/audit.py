SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "password",
    "password_confirmation",
    "provider_payload",
    "secret",
    "token",
}
REDACTED_VALUE = "[REDACTED]"


def redact_audit_metadata(metadata):
    if not isinstance(metadata, dict):
        raise TypeError("Audit metadata must be a dictionary.")

    return {
        str(key): _redact_value(key, value)
        for key, value in metadata.items()
    }


def _redact_value(key, value):
    normalized_key = str(key).lower().replace("-", "_")
    if normalized_key in SENSITIVE_KEYS or any(
        fragment in normalized_key for fragment in ("password", "secret", "token")
    ):
        return REDACTED_VALUE
    if isinstance(value, dict):
        return redact_audit_metadata(value)
    if isinstance(value, list):
        return [_redact_value(key, item) for item in value]
    return value
