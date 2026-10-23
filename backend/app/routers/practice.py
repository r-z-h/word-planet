import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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

router = APIRouter(prefix="/api/practice", tags=["practice"])


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

    update_wrong_book(db, user.id, question.id, correct)
    touch_streak(db, user.id, had_correct_today, correct)

    db.refresh(record)
    db.commit()

    return PracticeResultResponse(
        is_correct=correct,
        correct_answer=str(question.answer),
        explanation=question.explanation,
        consecutive_correct=record.consecutive_correct,
        mastered=record.consecutive_correct >= MASTERY_STREAK,
        duplicated=False,
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
