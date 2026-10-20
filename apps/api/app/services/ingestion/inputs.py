"""First-slice input policy; original bytes are retained without normalization."""

from app.core.errors import PublicError

MAX_SOURCE_BYTES = 8 * 1024 * 1024
UPLOAD_SECONDS = 60


SIGNATURES = {"pdf": b"%PDF-", "epub": b"PK\x03\x04"}


def validate_source(data: bytes, source_format: str) -> None:
    if source_format not in SIGNATURES:
        validate_text_source(data)
    elif len(data) > MAX_SOURCE_BYTES:
        raise PublicError(413, "SOURCE_TOO_LARGE", "Source exceeds the upload limit.")
    elif not data.startswith(SIGNATURES[source_format]):
        raise PublicError(422, "INVALID_SOURCE", "Source does not match its declared format.")


def validate_text_source(data: bytes) -> str:
    if len(data) > MAX_SOURCE_BYTES:
        raise PublicError(413, "SOURCE_TOO_LARGE", "Source exceeds the upload limit.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise PublicError(422, "INVALID_SOURCE", "Source must be UTF-8 text.") from None
    if (not text.strip("\ufeff \r\n\t") or data.startswith((b"%PDF-", b"PK\x03\x04"))
            or any(ord(char) < 32 and char not in "\t\n\r\f" for char in text)):
        raise PublicError(422, "INVALID_SOURCE", "Source is not supported text.")
    return text
