"""Password hashing for portal (DB-backed) users."""
import bcrypt

MAX_BCRYPT_PASSWORD_BYTES = 72


def _password_bytes(plain: str) -> bytes:
    raw = plain.encode("utf-8")
    if len(raw) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password must be 72 bytes or fewer.")
    return raw


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), password_hash.encode("utf-8"))
    except ValueError:
        return False
