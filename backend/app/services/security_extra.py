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


# ---------------- 失败锁定 ----------------
# 规则：同一 IP+账号 60 秒内连续 5 次失败 → 锁 10 分钟；
# 解锁后再次触发 → 锁 30 分钟；之后 10/30 交替循环。
FAIL_WINDOW = 60
FAIL_THRESHOLD = 5
LOCK_STEPS = (600, 1800)  # 秒：10 分钟 / 30 分钟

_fails: dict[str, list[float]] = {}
_locks: dict[str, dict] = {}
_stage: dict[str, int] = {}


def fail_key(ip: str, account: str) -> str:
    return f'{ip}:{(account or "").strip().lower()}'


def _fmt_wait(seconds: int) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    if m and s:
        return f'{m} 分 {s} 秒'
    if m:
        return f'{m} 分钟'
    return f'{s} 秒'


def check_lock(key: str) -> None:
    rec = _locks.get(key)
    if not rec:
        return
    left = rec['until'] - time.time()
    if left <= 0:
        _locks.pop(key, None)
        return
    raise HTTPException(
        status_code=429,
        detail={
            'detail': f'操作过于频繁，已被临时锁定，请 {_fmt_wait(left)}后再试',
            'code': 'LOCKED',
            'retry_after': int(left),
        },
    )


def record_failure(key: str) -> None:
    now = time.time()
    arr = [t for t in _fails.get(key, []) if now - t < FAIL_WINDOW]
    arr.append(now)
    if len(arr) < FAIL_THRESHOLD:
        _fails[key] = arr
        return
    # 触发锁定：10/30 交替
    stage = _stage.get(key, 0)
    duration = LOCK_STEPS[stage % len(LOCK_STEPS)]
    _stage[key] = stage + 1
    _locks[key] = {'until': now + duration}
    _fails[key] = []


def record_success(key: str) -> None:
    _fails.pop(key, None)


def lock_remaining_for_account(account: str) -> int:
    """管理员列表用：该账号任意 IP 的最长剩余锁定秒数。"""
    suffix = ':' + (account or '').strip().lower()
    now = time.time()
    best = 0
    for k, rec in list(_locks.items()):
        if k.endswith(suffix):
            best = max(best, int(rec['until'] - now))
    return max(0, best)


def clear_lock_for_account(account: str) -> int:
    suffix = ':' + (account or '').strip().lower()
    removed = 0
    for k in list(_locks.keys()):
        if k.endswith(suffix):
            _locks.pop(k, None)
            removed += 1
    for k in list(_fails.keys()):
        if k.endswith(suffix):
            _fails.pop(k, None)
    for k in list(_stage.keys()):
        if k.endswith(suffix):
            _stage.pop(k, None)
    return removed


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
