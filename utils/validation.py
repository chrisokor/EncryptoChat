import base64
import re


USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,31}$")
PREKEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-=]{8,80}$")


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username must start with a letter and contain 3-32 letters, numbers, or underscores.")
    return username


def validate_base64_key(value: str, expected_bytes: int) -> str:
    try:
        decoded = base64.b64decode(value.encode(), validate=True)
    except Exception as exc:
        raise ValueError("Value must be valid base64.") from exc
    if len(decoded) != expected_bytes:
        raise ValueError(f"Decoded value must be {expected_bytes} bytes.")
    return value


def validate_ciphertext(value: str) -> str:
    try:
        decoded = base64.b64decode(value.encode(), validate=True)
    except Exception as exc:
        raise ValueError("Ciphertext must be valid base64.") from exc
    if not decoded:
        raise ValueError("Ciphertext cannot be empty.")
    if len(decoded) > 65536:
        raise ValueError("Ciphertext cannot exceed 65536 bytes.")
    return value


def validate_prekey_id(value: str) -> str:
    if not PREKEY_ID_PATTERN.fullmatch(value):
        raise ValueError("Prekey id contains invalid characters.")
    return value
