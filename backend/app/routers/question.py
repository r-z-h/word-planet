import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Progress, Question, User, WrongQuestion
from ..schemas import AnswerSubmitRequest, AnswerSubmitResponse, QuestionNextResponse
from ..services.attempt_flow import apply_attempt
from ..services.attempts import MASTERY_STREAK
from ..services.judge import is_correct as judge_correct

router = APIRouter(prefix="/api", tags=["question"])


def _kp_payload(kp: KnowledgePoint | None) -> dict | None:
    if kp is None:
        return None
    return {
        "id": str(kp.id),
        "level": kp.level,
        "name": kp.name,
        "question_type": kp.question_type,
    }


def _current_kp(db: Session, user: User) -> KnowledgePoint:
    progress = db.get(Progress, user.id)
    if progress is None or progress.current_knowledge_point_id is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "没有当前知识点", "code": "NO_CURRENT_KNOWLEDGE_POINT"},
        )
    kp = db.get(KnowledgePoint, progress.current_knowledge_point_id)
    if kp is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "没有当前知识点", "code": "NO_CURRENT_KNOWLEDGE_POINT"},
        )
    return kp


def _base_pool(kp_id: uuid.UUID):
    return select(Question).where(
        Question.knowledge_point_id == kp_id,
        Question.question_type != "pronunciation",
    )


@router.get("/question/next", response_model=QuestionNextResponse)
def next_question(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    kp = _current_kp(db, user)

    if kp.question_type == "pronunciation":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "当前知识点是跟读，请调用 /api/pronunciation/next",
                "code": "USE_PRONUNCIATION_ENDPOINT",
            },
        )

    total = db.execute(
        select(func.count()).select_from(Question).where(Question.knowledge_point_id == kp.id)
    ).scalar_one()
    if total == 0:
        raise HTTPException(
            status_code=409,
            detail={"detail": "当前知识点没有题目", "code": "EMPTY_KNOWLEDGE_POINT"},
        )

    question = db.execute(
        _base_pool(kp.id)
        .join(WrongQuestion, WrongQuestion.question_id == Question.id)
        .where(
            WrongQuestion.user_id == user.id,
            WrongQuestion.consecutive_correct < MASTERY_STREAK,
        )
        .order_by(WrongQuestion.error_count.desc())
        .limit(1)
    ).scalar_one_or_none()

    if question is None:
        answered = select(Attempt.question_id).where(Attempt.user_id == user.id)
        question = db.execute(
            _base_pool(kp.id)
            .where(Question.id.notin_(answered))
            .order_by(func.random())
            .limit(1)
        ).scalar_one_or_none()

    if question is None:
        question = db.execute(
            select(Question)
            .join(WrongQuestion, WrongQuestion.question_id == Question.id)
            .where(
                WrongQuestion.user_id == user.id,
                WrongQuestion.consecutive_correct < MASTERY_STREAK,
                Question.knowledge_point_id != kp.id,
                Question.question_type != "pronunciation",
            )
            .order_by(WrongQuestion.error_count.desc())
            .limit(1)
        ).scalar_one_or_none()

    if question is None:
        question = db.execute(_base_pool(kp.id).order_by(func.random()).limit(1)).scalar_one_or_none()

    if question is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "当前知识点没有题目", "code": "EMPTY_KNOWLEDGE_POINT"},
        )

    return QuestionNextResponse(
        question={
            "id": str(question.id),
            "question_type": question.question_type,
            "stem": question.stem,
            "options": question.options,
            "knowledge_point_id": str(question.knowledge_point_id),
        }
    )


@router.post("/answer/submit", response_model=AnswerSubmitResponse)
def submit_answer(
    payload: AnswerSubmitRequest,
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
        progress = db.get(Progress, user.id)
        kp = db.get(KnowledgePoint, progress.current_knowledge_point_id) if progress else None
        return AnswerSubmitResponse(
            is_correct=existing.is_correct,
            correct_answer=str(question.answer) if question else "",
            progress_advanced=False,
            current_knowledge_point=_kp_payload(kp),
            new_badges=[],
            duplicated=True,
        )

    try:
        question_id = uuid.UUID(payload.question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id 非法")

    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question.question_type == "pronunciation":
        raise HTTPException(
            status_code=409,
            detail={"detail": "跟读题请调用 /api/pronunciation/result", "code": "WRONG_ENDPOINT"},
        )

    correct = judge_correct(question, payload.answer)
    result = apply_attempt(
        db,
        user,
        question,
        is_correct=correct,
        question_type="question",
        idempotency_key=payload.idempotency_key,
    )
    db.commit()

    return AnswerSubmitResponse(
        is_correct=correct,
        correct_answer=str(question.answer),
        progress_advanced=result["progress_advanced"],
        current_knowledge_point=_kp_payload(result["current_knowledge_point"]),
        new_badges=result["new_badges"],
        duplicated=False,
    )
