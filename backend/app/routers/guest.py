"""游客体验接口：无需账号、不写库，仅供试玩几个题。

- 不暴露答案：取题时只返回题干/选项/字母砖；提交后才判定。
- 不记录任何进度、错题、徽章、推送。
- 跟读（pronunciation）依赖麦克风+在线语音，游客版不开放。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KnowledgePoint, Question
from ..services.judge import is_correct as judge_correct
from ..services.security_extra import rate_limit
from ..services.tiles import tiles_for
from ..services.words import answer_text, word_payload

router = APIRouter(prefix="/api/guest", tags=["guest"])

# 游客不开放的题型（跟读要麦克风 + Google 语音，本地/公网都不稳）
GUEST_EXCLUDE_TYPES = {"pronunciation"}


class GuestAnswerRequest(BaseModel):
    question_id: str
    answer: str


def _module_payload(kp: KnowledgePoint, count: int) -> dict:
    return {
        "id": str(kp.id),
        "level": kp.level,
        "name": kp.name,
        "question_type": kp.question_type,
        "question_count": count,
    }


def _question_payload(q: Question) -> dict:
    tiles = None
    if q.question_type == "spelling":
        tiles = tiles_for(q.id, str(q.answer))
    return {
        "id": str(q.id),
        "question_type": q.question_type,
        "stem": q.stem,
        "options": q.options,
        "knowledge_point_id": str(q.knowledge_point_id),
        "tiles": tiles,
    }


@router.get("/modules")
def list_modules(db: Session = Depends(get_db)):
    """可体验的模块（知识点）列表，排除跟读。"""
    kps = (
        db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.question_type.notin_(GUEST_EXCLUDE_TYPES))
            .order_by(KnowledgePoint.level, KnowledgePoint.sort_order)
        )
        .scalars()
        .all()
    )
    modules = []
    for kp in kps:
        cnt = db.execute(
            select(func.count())
            .select_from(Question)
            .where(Question.knowledge_point_id == kp.id)
        ).scalar_one()
        if cnt > 0:
            modules.append(_module_payload(kp, int(cnt)))
    return {"modules": modules}


@router.get("/questions")
def get_questions(
    request: Request,
    kp_id: str,
    count: int = 3,
    db: Session = Depends(get_db),
):
    """按模块随机取 count 道题（不含答案）。"""
    rate_limit(request, "guest_pick", limit=120)
    try:
        kid = uuid.UUID(kp_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="kp_id 非法")
    kp = db.get(KnowledgePoint, kid)
    if kp is None:
        raise HTTPException(status_code=404, detail="模块不存在")
    if kp.question_type in GUEST_EXCLUDE_TYPES:
        raise HTTPException(status_code=400, detail="该模块暂不开放游客体验")

    try:
        n = int(count)
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(n, 10))

    questions = (
        db.execute(
            select(Question)
            .where(Question.knowledge_point_id == kid)
            .order_by(func.random())
            .limit(n)
        )
        .scalars()
        .all()
    )
    return {
        "module": _module_payload(kp, len(questions)),
        "questions": [_question_payload(q) for q in questions],
    }


@router.post("/answer")
def answer(req: GuestAnswerRequest, request: Request, db: Session = Depends(get_db)):
    """判定对错并返回义项；不写任何数据。"""
    rate_limit(request, "guest_answer", limit=120)
    try:
        qid = uuid.UUID(req.question_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="question_id 非法")
    q = db.get(Question, qid)
    if q is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    correct = judge_correct(q, req.answer or "")
    text = answer_text(q)
    return {
        "is_correct": correct,
        "correct_answer": text,
        "answer_text": text,
        "word": word_payload(db, q),
    }
