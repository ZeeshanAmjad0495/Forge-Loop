import secrets
from datetime import datetime, timezone, timedelta

import jwt
from fastapi import Header, HTTPException

from . import config


def _require_secret() -> str:
    secret = config.AUTH_TOKEN_SECRET
    if not secret:
        raise HTTPException(status_code=500, detail="Auth misconfigured: AUTH_TOKEN_SECRET not set")
    return secret


def create_access_token(email: str) -> str:
    secret = _require_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(seconds=config.AUTH_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    secret = _require_secret()
    return jwt.decode(token, secret, algorithms=["HS256"])


def verify_credentials(email: str, password: str) -> bool:
    if not config.AUTH_ADMIN_EMAIL or not config.AUTH_ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="Auth misconfigured: admin credentials not set")
    email_ok = secrets.compare_digest(email.lower().encode(), config.AUTH_ADMIN_EMAIL.lower().encode())
    password_ok = secrets.compare_digest(password.encode(), config.AUTH_ADMIN_PASSWORD.encode())
    return email_ok and password_ok


def require_auth(authorization: str | None = Header(default=None)) -> str:
    if not config.AUTH_ENABLED:
        return "auth-disabled"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]
