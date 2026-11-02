"""密码哈希与 JWT 签发/校验。仅依赖标准库 + PyJWT，无额外原生依赖。"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os

import jwt

from .config import SECRET_KEY, TOKEN_TTL_HOURS

_ALGO = "HS256"
_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256，格式 pbkdf2_sha256$iterations$salt_b64$hash_b64"""
    if not password or len(password) < 6:
        raise ValueError("密码长度至少 6 位")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(iters)
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False


def create_access_token(user_id: int, company_id: int, role: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "cid": company_id,
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[_ALGO])
