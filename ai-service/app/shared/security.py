"""Primitivos de segurança do auth (DEC-ORB-037): token de sessão opaco + OTP hasheado (HMAC+pepper)."""
import hashlib
import hmac
import secrets

from app.shared.config import get_settings


def new_session_token() -> str:
    """Token de sessão opaco (256 bits). Guardado no banco só como `token_pk` (sha256)."""
    return secrets.token_urlsafe(32)


def token_pk(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def gen_otp(length: int = 5) -> str:
    return f"{secrets.randbelow(10 ** length):0{length}d}"


def _pepper() -> bytes:
    settings = get_settings()
    if settings.auth_pepper:
        return settings.auth_pepper.encode()
    if settings.environment == "local":
        return b"dev-pepper-local-only"
    raise RuntimeError("auth_pepper é obrigatório fora de environment=local (fail-closed).")


def otp_hash(email: str, code: str) -> str:
    return hmac.new(_pepper(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def otp_matches(email: str, code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(otp_hash(email, code), stored_hash)
