"""讯飞（iFlytek）语音评测 / 实时转写封装。

未配置 key（settings.iflytek_enabled 为 False 或缺 app_id）时，全部走 mock：
mock 只用于把前端链路跑通，不产生真实评分。配好 .env 后自动切真实接口。

真实接口要点（等待 key 后按控制台参数校对）：
- 语音评测（一句话）HTTP：X-Appid / X-CurTime / X-Param(base64 JSON) / X-CheckSum=md5(apiKey+curTime+param)
- 实时转写（IAT）WebSocket：wss://iat-api.xfyun.cn/v2/iat，鉴权 URL 用 RFC1123 时间 + HMAC-SHA256
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from email.utils import format_datetime

import httpx

from ..config import settings

ISE_URL = "https://api.xfyun.cn/v1/service/v1/ise"
IAT_HOST = "iat-api.xfyun.cn"
IAT_PATH = "/v2/iat"


def is_configured() -> bool:
    return bool(
        settings.iflytek_enabled
        and settings.iflytek_app_id
        and settings.iflytek_api_key
        and settings.iflytek_api_secret
    )


def _ise_headers(param: dict) -> dict:
    cur_time = str(int(time.time()))
    param_b64 = base64.b64encode(json.dumps(param, ensure_ascii=False).encode("utf-8")).decode()
    check = hashlib.md5(
        (settings.iflytek_api_key + cur_time + param_b64).encode("utf-8")
    ).hexdigest()
    return {
        "X-Appid": settings.iflytek_app_id,
        "X-CurTime": cur_time,
        "X-Param": param_b64,
        "X-CheckSum": check,
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }


def _mock_score(pcm: bytes, ref_text: str) -> dict:
    """无 key 时的占位评分：稳定但不随机跳（同一段音频分数固定）。"""
    seed = hashlib.md5(pcm[:2048] + ref_text.encode("utf-8")).digest()[0]
    score = 72 + seed % 25  # 72~96
    return {
        "score": score,
        "stars": 5 if score >= 90 else 4 if score >= 80 else 3 if score >= 70 else 2 if score >= 60 else 1,
        "recognized": ref_text,
        "source": "mock",
    }


def _ise_ws_assess(pcm: bytes, ref_text: str, lang: str = "en_us") -> dict:
    """讯飞「语音评测」WebSocket（open-ise）。成功返回解析后的分数。"""
    import asyncio

    import websockets

    async def run() -> dict:
        url = _ise_auth_url()
        # 英文单词：BOM + [word]换行 + 单词
        text = "\ufeff[word]\n" + ref_text
        business = {
            "sub": "ise",
            "ent": "en_vip",
            "category": "read_word",
            "cmd": "ssb",
            "auf": "audio/L16;rate=16000",
            "aue": "raw",
            "text": text,
            "tte": "utf-8",
            "ttp_skip": True,
            "rstcd": "utf8",
            "rst": "plain",
        }
        # 每帧 audio 不超过 19200B；16k 采样 → 每帧 12800B（约 0.4s）
        step = 12800
        chunks = [pcm[i : i + step] for i in range(0, len(pcm), step)] or [b""]
        async with websockets.connect(url, open_timeout=12) as ws:
            await ws.send(
                json.dumps(
                    {
                        "common": {"app_id": settings.iflytek_app_id},
                        "business": business,
                        "data": {"status": 0},
                    }
                )
            )
            await asyncio.wait_for(ws.recv(), timeout=15)
            for idx, ch in enumerate(chunks):
                first = idx == 0
                last = idx == len(chunks) - 1
                payload = {
                    "business": {"cmd": "auw", "aus": 4 if last else (1 if first else 2)},
                    "data": {
                        "status": 2 if last else 1,
                        "data": base64.b64encode(ch).decode(),
                    },
                }
                await ws.send(json.dumps(payload))
                await asyncio.sleep(0.04)
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=20)
                d = json.loads(raw)
                if d.get("code") != 0:
                    raise RuntimeError(f"ise {d.get('code')}: {d.get('message')}")
                data = d.get("data") or {}
                if data.get("status") == 2 and data.get("data"):
                    return base64.b64decode(data["data"]).decode("utf-8", "ignore")

    xml_text = asyncio.run(run())
    import re

    m = re.search(r'total_score\s+value="([\d.]+)"', xml_text or "")
    if not m:
        raise RuntimeError("ise: 未找到 total_score")
    raw = float(m.group(1))
    # 讯飞英文评测(en_vip)的 total_score 是 5 分制；中文等为百分制。
    # 用 ≤5 判断并换算成百分制（4.846 → 96.9 分）。
    score = raw * 20 if raw <= 5.0 else raw
    score = int(round(max(0.0, min(100.0, score))))
    return {
        "score": score,
        "stars": 5 if score >= 90 else 4 if score >= 80 else 3 if score >= 70 else 2 if score >= 60 else 1,
        "recognized": ref_text,
        "source": "iflytek",
    }


def _ise_auth_url() -> str:
    from urllib.parse import quote

    host = "ise-api.xfyun.cn"
    path = "/v2/open-ise"
    date = format_datetime(datetime.now(timezone.utc), usegmt=True)
    origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    sign = base64.b64encode(
        hmac.new(settings.iflytek_api_secret.encode(), origin.encode(), hashlib.sha256).digest()
    ).decode()
    auth = base64.b64encode(
        (
            f'api_key="{settings.iflytek_api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{sign}"'
        ).encode()
    ).decode()
    return (
        f"wss://{host}{path}?authorization={quote(auth, safe='')}"
        f"&date={quote(date, safe='')}&host={host}"
    )


def _normalize_pcm(pcm: bytes) -> bytes:
    """音量归一化：峰值拉到 ~0.8，避免录音偏小被判低分。"""
    import struct

    if len(pcm) < 2:
        return pcm
    n = len(pcm) // 2
    vals = struct.unpack("<%dh" % n, pcm[: n * 2])
    peak = max((abs(v) for v in vals), default=0)
    if peak <= 0:
        return pcm
    target = 0.8 * 32767
    scale = target / peak
    if scale <= 1.2:
        return pcm
    out = [max(-32768, min(32767, int(v * scale))) for v in vals]
    return struct.pack("<%dh" % n, *out)


def assess_pcm(pcm: bytes, ref_text: str, lang: str = "en_us") -> dict:
    """一句话发音评测。返回 {score, stars, recognized, source}。失败直接抛异常（不造假分）。"""
    if not is_configured():
        raise RuntimeError("讯飞未配置（IFLYTEK_ENABLED / APP_ID / API_KEY / API_SECRET 缺失）")
    pcm = _normalize_pcm(pcm)
    return _ise_ws_assess(pcm, ref_text, lang)


def iat_auth_url() -> str:
    """生成讯飞 IAT WebSocket 鉴权 URL。"""
    from urllib.parse import quote

    date = format_datetime(datetime.now(timezone.utc), usegmt=True)
    origin = f"host: {IAT_HOST}\ndate: {date}\nGET {IAT_PATH} HTTP/1.1"
    sign = base64.b64encode(
        hmac.new(settings.iflytek_api_secret.encode(), origin.encode(), hashlib.sha256).digest()
    ).decode()
    auth = base64.b64encode(
        (
            f'api_key="{settings.iflytek_api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{sign}"'
        ).encode()
    ).decode()
    return (
        f"wss://{IAT_HOST}{IAT_PATH}"
        f"?authorization={quote(auth, safe='')}"
        f"&date={quote(date, safe='')}"
        f"&host={IAT_HOST}"
    )
