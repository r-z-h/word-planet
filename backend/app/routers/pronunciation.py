import asyncio
import base64
import json
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Progress, Question, User, Word
from ..schemas import (
    PronunciationNextResponse,
    PronunciationQuestionOut,
    PronunciationResultRequest,
    PronunciationResultResponse,
    PronunciationScoreResponse,
)
from ..security import decode_access_token
from ..services import iflytek
from ..services.attempt_flow import apply_attempt
from ..services.lesson import current_set_no, is_set_complete, mark_set_complete
from ..services.words import answer_text, word_payload

router = APIRouter(prefix="/api/pronunciation", tags=["pronunciation"])


def _require_pronunciation_kp(db: Session, user: User) -> KnowledgePoint:
    progress = db.get(Progress, user.id)
    if progress is None or progress.current_knowledge_point_id is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "没有当前知识点", "code": "NO_CURRENT_KNOWLEDGE_POINT"},
        )
    kp = db.get(KnowledgePoint, progress.current_knowledge_point_id)
    if kp is None or kp.question_type != "pronunciation":
        raise HTTPException(
            status_code=409,
            detail={"detail": "当前知识点不是跟读", "code": "WRONG_ENDPOINT"},
        )
    return kp


@router.get("/next", response_model=PronunciationNextResponse)
def next_pronunciation(
    exclude_id: str | None = None,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    kp = _require_pronunciation_kp(db, user)

    excluded_ids: list[uuid.UUID] = []
    if exclude_id:
        for part in exclude_id.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                excluded_ids.append(uuid.UUID(part))
            except ValueError:
                raise HTTPException(status_code=422, detail="exclude_id 非法")

    set_no = current_set_no(db, user.id, kp.id)
    if set_no is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "这个知识点的跟读题都练完了", "code": "KNOWLEDGE_POINT_FINISHED"},
        )

    # 与主流程一致：答过（对错都算）就不再出现，随机抽取避免固定顺序
    answered = select(Attempt.question_id).where(Attempt.user_id == user.id)
    stmt = select(Question).where(
        Question.knowledge_point_id == kp.id,
        Question.set_no == set_no,
        Question.question_type == "pronunciation",
        Question.id.notin_(answered),
    )
    if excluded_ids:
        stmt = stmt.where(Question.id.notin_(excluded_ids))
    question = db.execute(stmt.order_by(func.random()).limit(1)).scalar_one_or_none()

    if question is None:
        if is_set_complete(db, user.id, kp.id, set_no):
            mark_set_complete(db, user, kp, set_no)
            db.commit()
        raise HTTPException(
            status_code=409,
            detail={"detail": "这一套跟读练完了", "code": "SET_FINISHED"},
        )

    progress = db.get(Progress, user.id)
    if progress is not None and progress.last_question_id != question.id:
        progress.last_question_id = question.id
        db.commit()

    total = db.execute(
        select(func.count())
        .select_from(Question)
        .where(Question.knowledge_point_id == kp.id, Question.set_no == set_no)
    ).scalar_one()
    done = db.execute(
        select(func.count(func.distinct(Attempt.question_id)))
        .select_from(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .where(
            Attempt.user_id == user.id,
            Question.knowledge_point_id == kp.id,
            Question.set_no == set_no,
            Attempt.question_type != "practice",
        )
    ).scalar_one()

    word = db.execute(
        select(Word).where(Word.word == str(question.answer).strip().lower())
    ).scalar_one_or_none()

    return PronunciationNextResponse(
        question=PronunciationQuestionOut(
            id=str(question.id),
            stem=question.stem,
            answer=str(question.answer),
            phonetic=word.phonetic if word else None,
        ),
        set_no=set_no,
        set_total=total,
        set_done=done,
        knowledge_point_name=kp.name,
    )

@router.post("/result", response_model=PronunciationResultResponse)
def submit_pronunciation(
    payload: PronunciationResultRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(Attempt).where(
            Attempt.user_id == user.id, Attempt.idempotency_key == payload.idempotency_key
        )
    ).scalar_one_or_none()
    if existing is not None:
        question = db.get(Question, existing.question_id)
        return PronunciationResultResponse(
            recorded=True,
            progress_advanced=False,
            new_badges=[],
            duplicated=True,
            answer_text=answer_text(question) if question else None,
            word=word_payload(db, question) if question else None,
        )

    try:
        question_id = uuid.UUID(payload.word_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="word_id 非法")

    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.question_type != "pronunciation":
        raise HTTPException(
            status_code=409,
            detail={"detail": "不是跟读题", "code": "WRONG_ENDPOINT"},
        )

    _require_pronunciation_kp(db, user)

    result = apply_attempt(
        db,
        user,
        question,
        is_correct=payload.is_correct,
        question_type="pronunciation",
        idempotency_key=payload.idempotency_key,
    )

    progress = db.get(Progress, user.id)
    if progress is not None and progress.last_question_id == question.id:
        progress.last_question_id = None

    db.commit()

    return PronunciationResultResponse(
        recorded=True,
        progress_advanced=result["progress_advanced"],
        new_badges=result["new_badges"],
        duplicated=False,
        answer_text=answer_text(question),
        word=word_payload(db, question),
    )


class ReviewPronRequest(BaseModel):
    word_id: str
    is_correct: bool


@router.post("/review")
def review_pronunciation(
    payload: ReviewPronRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """跟读复习判题：只返回对错/义项，**不写任何数据**（不推进、不发奖励、不记错题）。"""
    try:
        qid = uuid.UUID(payload.word_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="word_id 非法")
    question = db.get(Question, qid)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.question_type != "pronunciation":
        raise HTTPException(
            status_code=409,
            detail={"detail": "不是跟读题", "code": "WRONG_ENDPOINT"},
        )
    return {
        "is_correct": bool(payload.is_correct),
        "correct_answer": answer_text(question),
        "answer_text": answer_text(question),
        "word": word_payload(db, question),
    }


@router.post("/score", response_model=PronunciationScoreResponse)
def score_pronunciation(
    audio: UploadFile = File(...),
    word: str = Form(...),
    user: User = Depends(require_tested),
):
    """跟读评分：接收 PCM(16k 单声道 int16) 音频，返回发音分与星级。

    注意：这里必须是同步 def（FastAPI 会放到线程池），因为底层讯飞调用用
    asyncio.run()；若写成 async def，会在已有事件循环里调用而报
    'asyncio.run() cannot be called from a running event loop'。
    """
    pcm = audio.file.read()
    if not pcm:
        raise HTTPException(
            status_code=422, detail={"detail": "音频为空", "code": "EMPTY_AUDIO"}
        )
    if not iflytek.is_configured():
        raise HTTPException(
            status_code=503,
            detail={"detail": "讯飞语音评分未配置", "code": "IFLYTEK_NOT_CONFIGURED"},
        )
    try:
        result = iflytek.assess_pcm(pcm, word.strip())
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"detail": f"语音评分失败：{exc}", "code": "IFLYTEK_SCORE_FAILED"},
        )
    return PronunciationScoreResponse(**result)


@router.websocket("/stream")
async def stream_subtitles(ws: WebSocket, word: str = "", token: str = ""):
    """流式字幕：边说边回识别文本（interim）。

    未配置讯飞时走 mock：按收到的音频块数量渐进返回目标词的子串。
    """
    user_id = decode_access_token(token) if token else None
    if not user_id:
        await ws.close(code=4401)
        return
    await ws.accept()

    if iflytek.is_configured():
        try:
            await _relay_iflytek(ws, word)
            return
        except WebSocketDisconnect:
            return
        except Exception:
            # 云端异常 → 退回 mock 字幕，保证页面不崩
            pass

    chunks = 0
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            data = msg.get("bytes")
            text = msg.get("text")
            if data:
                chunks += 1
                ratio = min(0.85, chunks / 8.0)
                partial = word[: max(1, int(len(word) * ratio))] if word else ""
                await ws.send_json({"type": "interim", "text": partial})
            elif text == "END":
                await ws.send_json({"type": "final", "text": word})
                break
    except WebSocketDisconnect:
        return


async def _relay_iflytek(ws: WebSocket, word: str):
    """把浏览器音频分片转发给讯飞 IAT，并把识别文本回推（真实流式）。"""
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
            while True:
                item = await queue.get()
                if item is None:
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
                    body["business"] = {"language": "en_us", "domain": "iat", "vad_eos": 3000}
                await up.send(json.dumps(body))

        async def receiver():
            text = ""
            async for raw in up:
                d = json.loads(raw)
                data = d.get("data") or {}
                result = data.get("result") or {}
                if result:
                    for seg in result.get("ws", []):
                        for cw in seg.get("cw", []):
                            text += cw.get("w", "")
                    await ws.send_json({"type": "interim", "text": text})
                if data.get("status") == 2:
                    await ws.send_json({"type": "final", "text": text or word})
                    return

        await asyncio.gather(pump_in(), sender(), receiver())
