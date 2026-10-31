"""轻量安全组件：算术验证码（HMAC 签名 token）+ 进程内频率限制。

说明：限流是**单进程内存**实现，够单机 uvicorn 使用；将来多 worker/多实例
需换 Redis（接口不变）。
"""

import base64
import hashlib
import hmac
import json
import random
import time

from fastapi import HTTPException, Request

from ..config import settings

CAPTCHA_TTL = 300  # 5 分钟


def _sign(payload: bytes) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload, hashlib.sha256).hexdigest()


def make_captcha() -> dict:
    a = random.randint(2, 9)
    b = random.randint(2, 9)
    ans = a + b
    body = json.dumps({'a': a, 'b': b, 'ans': ans, 'exp': int(time.time()) + CAPTCHA_TTL}, ensure_ascii=False)
    raw = base64.urlsafe_b64encode(body.encode()).decode()
    token = raw + '.' + _sign(body.encode())
    return {'token': token, 'question': f'{a} + {b} = ?'}


def verify_captcha(token: str | None, code: str | None) -> None:
    if not settings.require_captcha:
        return
    if not token or not code:
        raise HTTPException(status_code=422, detail={'detail': '请填写验证码', 'code': 'CAPTCHA_REQUIRED'})
    try:
        raw, sig = token.rsplit('.', 1)
        body = base64.urlsafe_b64decode(raw.encode())
        if not hmac.compare_digest(sig, _sign(body)):
            raise ValueError('bad sig')
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=422, detail={'detail': '验证码无效，请刷新', 'code': 'CAPTCHA_INVALID'})
    if time.time() > data.get('exp', 0):
        raise HTTPException(status_code=422, detail={'detail': '验证码已过期，请刷新', 'code': 'CAPTCHA_EXPIRED'})
    try:
        if int(str(code).strip()) != int(data['ans']):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=422, detail={'detail': '验证码不正确', 'code': 'CAPTCHA_WRONG'})


# ---------------- 频率限制 ----------------
_buckets: dict[str, list[float]] = {}


def rate_limit(request: Request, bucket: str, limit: int | None = None) -> None:
    """按 IP+桶 限制每分钟次数；settings.rate_limit_per_min=0 时关闭。"""
    limit = limit if limit is not None else settings.rate_limit_per_min
    if not limit:
        return
    ip = request.client.host if request.client else 'unknown'
    key = f'{bucket}:{ip}'
    now = time.time()
    arr = [t for t in _buckets.get(key, []) if now - t < 60]
    if len(arr) >= limit:
        raise HTTPException(status_code=429, detail={'detail': '操作太频繁，请稍后再试', 'code': 'RATE_LIMITED'})
    arr.append(now)
    _buckets[key] = arr
