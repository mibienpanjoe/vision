"""Versioned scrypt password hashes; settings are not user-controlled."""
import hashlib
import hmac
import secrets


def derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=131072, r=8, p=1,
                          dklen=64, maxmem=256 * 1024 * 1024)


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Use a passphrase between 12 and 128 characters")
    salt = secrets.token_bytes(16)
    return f"scrypt-v1${salt.hex()}${derive(password, salt).hex()}"


def verify_password(password: str, encoded: str) -> bool:
    if len(password) > 128:
        return False
    try:
        version, salt_hex, expected_hex = encoded.split("$")
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(expected_hex)
        if version != "scrypt-v1" or len(salt) != 16 or len(expected) != 64:
            raise ValueError("Invalid stored hash")
    except ValueError:
        # Unknown accounts use the same expensive operation as existing ones.
        salt, expected = bytes(16), bytes(64)
    return hmac.compare_digest(derive(password, salt), expected)
