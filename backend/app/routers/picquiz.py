import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Question, SetProgress, User
from ..services import rewards

router = APIRouter(prefix="/api/picquiz", tags=["picquiz"])


class PicQuizAnswer(BaseModel):
    question_id: str
    answer: str


def _picquiz_kp(db: Session) -> KnowledgePoint | None:
    return db.execute(
        select(KnowledgePoint).where(KnowledgePoint.name == "看图猜词")
    ).scalar_one_or_none()


@router.get("/questions")
def questions(db: Session = Depends(get_db)):
    kp = _picquiz_kp(db)
    if kp is None:
        return {"sets": [], "questions": []}
    qs = (
        db.execute(
            select(Question)
            .where(Question.knowledge_point_id == kp.id)
            .order_by(Question.set_no)
        )
        .scalars()
        .all()
    )
    out = []
    counts: dict[int, int] = {}
    for q in qs:
        opts = list((q.options or {}).values())
        out.append({
            "id": str(q.id),
            "set_no": q.set_no,
            "word": q.stem,
            "cn": (q.explanation or "").split(" = ")[-1],
            "options": opts,
        })
        counts[q.set_no] = counts.get(q.set_no, 0) + 1
    return {
        "sets": [{"set_no": k, "count": v} for k, v in sorted(counts.items())],
        "questions": out,
    }


@router.post("/answer")
def answer(
    payload: PicQuizAnswer,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """看图猜词：只判对错 + 记一条作答；**不记花/星**。

    「一套全对」= 该套即算满星完成（SetProgress.is_complete=True），
    徽记数 = 满星套数（在 set_summary 里按 picquiz 特判），故无需花/星兑换。
    """
    try:
        qid = uuid.UUID(payload.question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id 非法")
    q = db.get(Question, qid)
    if q is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    opts = q.options or {}
    correct = payload.answer == opts.get(q.answer)

    db.add(
        Attempt(
            user_id=user.id,
            question_id=q.id,
            question_type="picquiz",
            idempotency_key="picquiz-" + uuid.uuid4().hex,
            is_correct=correct,
        )
    )
    db.flush()

    sp = rewards.get_set_progress(db, user.id, q.knowledge_point_id, q.set_no)
    if sp is None:
        total = db.execute(
            select(func.count())
            .select_from(Question)
            .where(
                Question.knowledge_point_id == q.knowledge_point_id,
                Question.set_no == q.set_no,
            )
        ).scalar_one()
        sp = SetProgress(
            user_id=user.id,
            knowledge_point_id=q.knowledge_point_id,
            set_no=q.set_no,
            total_count=int(total),
        )
        db.add(sp)
        db.flush()

    rewards.recompute_set_progress(db, user.id, q.knowledge_point_id, q.set_no)
    db.commit()

    sp2 = rewards.get_set_progress(db, user.id, q.knowledge_point_id, q.set_no)
    return {
        "is_correct": correct,
        "word": q.stem,
        "cn": (q.explanation or "").split(" = ")[-1],
        "set_complete": bool(sp2 and sp2.is_complete),
    }
