import uuid
from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import (
    Attempt,
    KnowledgePoint,
    Progress,
    Question,
    User,
    WrongQuestion,
)
from ..schemas import (
    PracticeNextResponse,
    PracticeQuestionOut,
    PracticeResultRequest,
    PracticeResultResponse,
)
from ..services.attempt_flow import update_wrong_book
from ..services.attempts import (
    MASTERY_STREAK,
    had_correct_attempt_today,
    touch_streak,
)
from ..services.judge import is_correct as judge_correct
from ..services import rewards

router = APIRouter(prefix="/api/practice", tags=["practice"])

# 防抢记：同一题两次「答对」至少间隔这么多分钟，才计下一次连对
PRACTICE_COOLDOWN_MINUTES = 10


def _wrong_pool(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID | None):
    stmt = (
        select(WrongQuestion, Question, KnowledgePoint)
        .join(Question, Question.id == WrongQuestion.question_id)
        .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
        .where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.consecutive_correct < MASTERY_STREAK,
        )
    )
    if kp_id is not None:
        stmt = stmt.where(Question.knowledge_point_id == kp_id)
    return stmt.order_by(WrongQuestion.error_count.desc(), WrongQuestion.last_wrong_at)


@router.get("/next", response_model=PracticeNextResponse)
def next_practice(
    knowledge_point_id: str | None = None,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    kp_id = None
    if knowledge_point_id:
        try:
            kp_id = uuid.UUID(knowledge_point_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="knowledge_point_id 非法")

    row = db.execute(_wrong_pool(db, user.id, kp_id).limit(1)).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "没有待练习的错题", "code": "NO_WRONG_QUESTIONS"},
        )

    wrong, question, kp = row
    return PracticeNextResponse(
        question=PracticeQuestionOut(
            id=str(question.id),
            question_type=question.question_type,
            stem=question.stem,
            options=question.options,
            explanation=question.explanation,
            error_count=wrong.error_count,
            consecutive_correct=wrong.consecutive_correct,
            knowledge_point_name=kp.name,
        ),
        remaining=db.execute(
            _wrong_pool(db, user.id, kp_id).limit(1000)
        ).all().__len__(),
    )


@router.get("/one", response_model=PracticeNextResponse)
def one_practice(
    question_id: str,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """按题目 ID 取一道错题，用于错题本里「单独练这一题」。"""
    try:
        qid = uuid.UUID(question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id 非法")
    question = db.get(Question, qid)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    record = db.execute(
        select(WrongQuestion).where(
            WrongQuestion.user_id == user.id, WrongQuestion.question_id == qid
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "这道题不在错题本里", "code": "NOT_IN_WRONG_BOOK"},
        )
    kp = db.get(KnowledgePoint, question.knowledge_point_id)
    remaining = db.execute(_wrong_pool(db, user.id, None).limit(1000)).all().__len__()
    return PracticeNextResponse(
        question=PracticeQuestionOut(
            id=str(question.id),
            question_type=question.question_type,
            stem=question.stem,
            options=question.options,
            explanation=question.explanation,
            error_count=record.error_count,
            consecutive_correct=record.consecutive_correct,
            knowledge_point_name=kp.name if kp else "",
        ),
        remaining=remaining,
    )


@router.post("/result", response_model=PracticeResultResponse)
def submit_practice(
    payload: PracticeResultRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(Attempt).where(
            Attempt.user_id == user.id,
            Attempt.idempotency_key == payload.idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        question = db.get(Question, existing.question_id)
        return PracticeResultResponse(
            is_correct=existing.is_correct,
            correct_answer=str(question.answer) if question else "",
            explanation=question.explanation if question else None,
            consecutive_correct=0,
            mastered=False,
            duplicated=True,
        )

    try:
        question_id = uuid.UUID(payload.question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id 非法")

    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    record = db.execute(
        select(WrongQuestion).where(
            WrongQuestion.user_id == user.id,
            WrongQuestion.question_id == question_id,
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "这道题不在错题本里", "code": "NOT_IN_WRONG_BOOK"},
        )

    correct = judge_correct(question, payload.answer)
    had_correct_today = had_correct_attempt_today(db, user.id) if correct else False

    # 防抢记：取该题上一次「练习答对」的时间
    prev_correct_at = db.execute(
        select(func.max(Attempt.created_at)).where(
            Attempt.user_id == user.id,
            Attempt.question_id == question.id,
            Attempt.question_type == "practice",
            Attempt.is_correct.is_(True),
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    db.add(
        Attempt(
            user_id=user.id,
            question_id=question.id,
            question_type="practice",
            idempotency_key=payload.idempotency_key,
            is_correct=correct,
        )
    )
    db.flush()

    counted = False
    cooldown_remaining = 0
    if not correct:
        record.error_count = (record.error_count or 0) + 1
        record.consecutive_correct = 0
        record.last_wrong_at = now
    else:
        too_soon = False
        if prev_correct_at is not None:
            prev = prev_correct_at
            if prev.tzinfo is None:
                prev = prev.replace(tzinfo=timezone.utc)
            gap = timedelta(minutes=PRACTICE_COOLDOWN_MINUTES)
            elapsed = now - prev
            if elapsed < gap:
                too_soon = True
                cooldown_remaining = int(ceil((gap - elapsed).total_seconds()))
        # 间隔太近：视为同一时间抢记，不累计连对（也不清零）
        if not too_soon:
            record.consecutive_correct = (record.consecutive_correct or 0) + 1
            counted = True

    flower_gained = False
    # 连续答对达到阈值 → 补发该题 1 朵花（幂等，每题只补一次）；纯练星球不产花
    kp = db.get(KnowledgePoint, question.knowledge_point_id)
    if (
        correct
        and (record.consecutive_correct or 0) >= MASTERY_STREAK
        and (kp is None or kp.produces_flowers)
    ):
        flower_gained = rewards.award_flower(db, user.id, question, source="practice")

    touch_streak(db, user.id, had_correct_today, correct)

    db.flush()
    db.refresh(record)
    db.commit()

    return PracticeResultResponse(
        is_correct=correct,
        correct_answer=str(question.answer),
        explanation=question.explanation,
        consecutive_correct=record.consecutive_correct,
        mastered=record.consecutive_correct >= MASTERY_STREAK,
        duplicated=False,
        mastered_needed=MASTERY_STREAK,
        counted=counted,
        cooldown_remaining=cooldown_remaining,
        flower_gained=flower_gained,
    )


@router.get("/summary")
def practice_summary(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    """错题本总览：待练习 / 已掌握 / 按知识点分布。"""
    rows = db.execute(
        select(WrongQuestion, Question, KnowledgePoint)
        .join(Question, Question.id == WrongQuestion.question_id)
        .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
        .where(WrongQuestion.user_id == user.id)
    ).all()

    progress = db.get(Progress, user.id)
    current_kp_id = str(progress.current_knowledge_point_id) if progress else None

    by_kp: dict[str, dict] = {}
    for wrong, _question, kp in rows:
        item = by_kp.setdefault(
            str(kp.id),
            {
                "knowledge_point_id": str(kp.id),
                "knowledge_point_name": kp.name,
                "level": kp.level,
                "pending": 0,
                "mastered": 0,
                "is_current": str(kp.id) == current_kp_id,
            },
        )
        if wrong.consecutive_correct >= MASTERY_STREAK:
            item["mastered"] += 1
        else:
            item["pending"] += 1

    items = sorted(by_kp.values(), key=lambda x: (not x["is_current"], -x["pending"]))
    return {
        "pending": sum(i["pending"] for i in items),
        "mastered": sum(i["mastered"] for i in items),
        "by_knowledge_point": items,
    }


# ---------------- 批量取题（错题强化 / 掌握度检测） ----------------

class RecheckRequest(BaseModel):
    question_id: str
    answer: str


@router.get("/batch")
def practice_batch(
    scope: str = "pending",
    knowledge_point_id: str | None = None,
    limit: int = 20,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """一次取一批错题：scope=pending(待练，按模块) / mastered(已掌握，不分模块)。随机、去重、上限50。"""
    scope = "mastered" if scope == "mastered" else "pending"
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 20
    n = max(1, min(n, 50))

    kp_id = None
    if knowledge_point_id:
        try:
            kp_id = uuid.UUID(knowledge_point_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="knowledge_point_id 非法")

    base = (
        select(WrongQuestion, Question, KnowledgePoint)
        .join(Question, Question.id == WrongQuestion.question_id)
        .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
        .where(WrongQuestion.user_id == user.id)
    )
    if scope == "pending":
        base = base.where(WrongQuestion.consecutive_correct < MASTERY_STREAK)
        if kp_id is not None:
            base = base.where(Question.knowledge_point_id == kp_id)
    else:
        base = base.where(WrongQuestion.consecutive_correct >= MASTERY_STREAK)
        if kp_id is not None:
            base = base.where(Question.knowledge_point_id == kp_id)

    rows = db.execute(base.order_by(func.random()).limit(n)).all()
    items = [
        {
            "id": str(q.id),
            "question_type": q.question_type,
            "stem": q.stem,
            "options": q.options,
            "explanation": q.explanation,
            "error_count": w.error_count,
            "consecutive_correct": w.consecutive_correct,
            "knowledge_point_name": kp.name,
        }
        for w, q, kp in rows
    ]
    return {"scope": scope, "count": len(items), "items": items}


@router.post("/recheck")
def practice_recheck(
    payload: RecheckRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """掌握度检测判题：答错→回炉待练，答对→保持掌握；不发奖励、不计连击/每日任务、不写 Attempt。"""
    try:
        qid = uuid.UUID(payload.question_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="question_id 非法")
    q = db.get(Question, qid)
    if q is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    record = db.execute(
        select(WrongQuestion).where(
            WrongQuestion.user_id == user.id, WrongQuestion.question_id == qid
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "这道题不在错题本里", "code": "NOT_IN_WRONG_BOOK"},
        )

    correct = judge_correct(q, payload.answer or "")
    update_wrong_book(db, user.id, q.id, correct)
    db.commit()
    db.refresh(record)
    return {
        "is_correct": correct,
        "correct_answer": str(q.answer),
        "explanation": q.explanation,
        "consecutive_correct": record.consecutive_correct,
        "mastered": record.consecutive_correct >= MASTERY_STREAK,
    }
