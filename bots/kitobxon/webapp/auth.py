import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import jwt
from fastapi import HTTPException

_ALGORITHM = "HS256"
_TTL = 900  # 15 min


def _verify_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram WebApp initData and return parsed user dict."""
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="no hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(status_code=401, detail="invalid hash")

    user_str = params.get("user", "{}")
    try:
        user = json.loads(user_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="invalid user json")

    if not user.get("id"):
        raise HTTPException(status_code=401, detail="no user id")

    return user


def create_token(telegram_id: int, secret: str) -> str:
    payload = {
        "sub": str(telegram_id),
        "iat": int(time.time()),
        "exp": int(time.time()) + _TTL,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def verify_token(token: str, secret: str) -> int:
    """Returns telegram_id or raises HTTPException."""
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
        return int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


def get_token_from_header(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    return authorization.removeprefix("Bearer ")


def verify_init_data_and_issue_token(init_data: str, bot_token: str, jwt_secret: str) -> tuple[int, str]:
    """Full auth flow: verify initData → return (telegram_id, jwt_token)."""
    user = _verify_init_data(init_data, bot_token)
    telegram_id = int(user["id"])
    token = create_token(telegram_id, jwt_secret)
    return telegram_id, token
