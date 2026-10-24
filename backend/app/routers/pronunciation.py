import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Progress, Question, User
from ..schemas import (
    PronunciationNextResponse,
    PronunciationQuestionOut,
    PronunciationResultRequest,
    PronunciationResultResponse,
)
from ..services.attempt_flow import apply_attempt
from ..services.lesson import current_set_no, is_set_complete, mark_set_complete

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

    return PronunciationNextResponse(
        question=PronunciationQuestionOut(
            id=str(question.id), stem=question.stem, answer=str(question.answer)
        )
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
        return PronunciationResultResponse(
            recorded=True, progress_advanced=False, new_badges=[], duplicated=True
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
    )
