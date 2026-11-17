"""系统问答助手接口。

- `POST /api/help/ask`：唯一提问入口（A 规则层 + B 独立 RAG 引擎）。
- `POST /api/help/reindex`：一键重建知识库索引并热加载（管理员）。
- `GET  /api/help/unmatched`：未命中问题排行（管理员），用于指导补知识库。
"""

from collections import Counter
import asyncio
import base64
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import User
from ..schemas import HelpAnswer, HelpAskRequest
from ..security import decode_access_token
from ..services import help as help_service
from ..services import iflytek

router = APIRouter(prefix="/api/help", tags=["help"])

logger = logging.getLogger("word_planet.asr")

_TTS_CACHE: dict = {}
_TTS_CACHE_MAX = 300

_UNMATCHED_LOG = Path(__file__).resolve().parents[3] / "data" / "logs" / "help_unmatched.jsonl"


@router.post("/ask", response_model=HelpAnswer)
def ask(
    payload: HelpAskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return help_service.answer(db, user, payload.question, payload.context)


class HelpTtsRequest(BaseModel):
    text: str


@router.post("/tts")
def help_tts(payload: HelpTtsRequest, user: User = Depends(get_current_user)):
    """把助手回答文字用讯飞合成成 mp3（童声 xiaoxin），供前端播放。"""
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text 为空")
    if len(text) > 600:
        text = text[:600]
    vcn = getattr(settings, "help_tts_vcn", "xiaoxin") or "xiaoxin"
    speed = int(getattr(settings, "help_tts_speed", 60) or 60)
    key = (vcn, speed, text)
    cached = _TTS_CACHE.get(key)
    if cached:
        return Response(content=cached, media_type="audio/mpeg")
    try:
        audio = iflytek.tts(text, vcn=vcn, speed=speed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("help tts failed: %s", exc)
        raise HTTPException(status_code=503, detail={"code": "TTS_UNAVAILABLE", "detail": str(exc)})
    if audio:
        if len(_TTS_CACHE) >= _TTS_CACHE_MAX:
            _TTS_CACHE.clear()
        _TTS_CACHE[key] = audio
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/reindex")
def reindex(_admin: User = Depends(require_admin)):
    """一键重建知识库索引并热加载（当前进程立即使用新索引，不用重启）。"""
    import rag_engine

    data = rag_engine.build_index()
    return {"ok": True, "count": data["count"], "dim": data["dim"]}


@router.get("/unmatched")
def unmatched(limit: int = 50, _admin: User = Depends(require_admin)):
    """未命中问题排行（只记问题文本，不记账号）。"""
    if not _UNMATCHED_LOG.exists():
        return {"items": [], "total": 0}
    rows = []
    for line in _UNMATCHED_LOG.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    counter = Counter(r.get("question", "") for r in rows if r.get("question"))
    items = [
        {"question": q, "count": n}
        for q, n in counter.most_common(max(1, min(limit, 200)))
    ]
    return {"items": items, "total": len(rows)}


# ---------------------------------------------------------------- 语音提问（ASR）


async def _relay_iat(ws: WebSocket, language: str = "zh_cn"):
    """把浏览器 PCM16(16k) 音频转发给讯飞 IAT，回推 interim/final 文本。"""
    import websockets

    queue: asyncio.Queue = asyncio.Queue()

    async def pump_in():
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                await queue.put(None)
                return
            if msg.get("bytes"):
                await queue.put(msg["bytes"])
            elif msg.get("text") == "END":
                await queue.put(None)
                return

    async with websockets.connect(iflytek.iat_auth_url()) as up:

        async def sender():
            frame = 0
            total = 0
            while True:
                item = await queue.get()
                if item is None:
                    logger.info("asr END: frames=%d bytes=%d", frame, total)
                    await up.send(
                        json.dumps(
                            {
                                "data": {
                                    "status": 2,
                                    "format": "audio/L16;rate=16000",
                                    "encoding": "raw",
                                    "audio": "",
                                }
                            }
                        )
                    )
                    return
                frame += 1
                total += len(item)
                body = {
                    "data": {
                        "status": 0 if frame == 1 else 1,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(item).decode(),
                    }
                }
                if frame == 1:
                    body["common"] = {"app_id": settings.iflytek_app_id}
                    body["business"] = {"language": language, "domain": "iat", "vad_eos": 3000}
                await up.send(json.dumps(body))

        async def receiver():
            text = ""
            async for raw in up:
                d = json.loads(raw)
                if d.get("code") not in (None, 0):
                    logger.warning(
                        "iflytek iat error code=%s msg=%s", d.get("code"), d.get("message")
                    )
                    try:
                        await ws.send_json(
                            {"type": "error", "code": "ASR_IFLYTEK_" + str(d.get("code"))}
                        )
                    except Exception:
                        pass
                    return
                data = d.get("data") or {}
                result = data.get("result") or {}
                if result:
                    for seg in result.get("ws", []):
                        for cw in seg.get("cw", []):
                            text += cw.get("w", "")
                    await ws.send_json({"type": "interim", "text": text})
                if data.get("status") == 2:
                    logger.info("asr final len=%d text=%r", len(text), text[:80])
                    await ws.send_json({"type": "final", "text": text})
                    return

        await asyncio.gather(pump_in(), sender(), receiver())


@router.websocket("/asr/stream")
async def asr_stream(websocket: WebSocket, token: str = ""):
    """语音提问：浏览器 PCM → 讯飞 IAT → 文本（zh_cn）。未配置讯飞则让前端兜底。"""
    user_id = decode_access_token(token) if token else None
    if not user_id:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    if not iflytek.is_configured():
        await websocket.send_json({"type": "error", "code": "ASR_UNAVAILABLE"})
        await websocket.close()
        return
    try:
        await _relay_iat(websocket, language="zh_cn")
    except WebSocketDisconnect:
        return
    except Exception:  # noqa: BLE001
        try:
            await websocket.send_json({"type": "error", "code": "ASR_ERROR"})
        except Exception:
            pass
