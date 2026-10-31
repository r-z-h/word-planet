import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Progress, Question, User
from ..schemas import AnswerSubmitRequest, AnswerSubmitResponse, QuestionNextResponse
from ..services.attempt_flow import apply_attempt
from ..services.judge import is_correct as judge_correct
from ..services.lesson import (
    current_set_no,
    is_set_complete,
    mark_set_complete,
    resolve_current_kp,
)
from ..services.words import answer_text, word_payload
from ..services import tiles as tiles_service

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


def _parse_exclude(value: str | None) -> list[uuid.UUID]:
    if not value:
        return []
    result: list[uuid.UUID] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(uuid.UUID(part))
        except ValueError:
            raise HTTPException(status_code=422, detail="exclude_id 非法")
    return result


def _set_counts(
    db: Session, user_id: uuid.UUID, kp_id: uuid.UUID, set_no: int
) -> tuple[int, int]:
    total = db.execute(
        select(func.count())
        .select_from(Question)
        .where(Question.knowledge_point_id == kp_id, Question.set_no == set_no)
    ).scalar_one()
    done = db.execute(
        select(func.count(func.distinct(Attempt.question_id)))
        .select_from(Attempt)
        .join(Question, Question.id == Attempt.question_id)
        .where(
            Attempt.user_id == user_id,
            Question.knowledge_point_id == kp_id,
            Question.set_no == set_no,
            Attempt.question_type != "practice",
        )
    ).scalar_one()
    return total, done


@router.get("/question/next", response_model=QuestionNextResponse)
def next_question(
    exclude_id: str | None = None,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    kp = resolve_current_kp(db, user)
    if kp is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "没有当前知识点", "code": "NO_CURRENT_KNOWLEDGE_POINT"},
        )

    if kp.question_type == "pronunciation":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "当前知识点是跟读，请调用 /api/pronunciation/next",
                "code": "USE_PRONUNCIATION_ENDPOINT",
            },
        )

    excluded = _parse_exclude(exclude_id)
    progress = db.get(Progress, user.id)

    for _ in range(50):
        set_no = current_set_no(db, user.id, kp.id)
        if set_no is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "这个知识点的题都学完了",
                    "code": "KNOWLEDGE_POINT_FINISHED",
                },
            )

        question = None
        if progress is not None and progress.last_question_id is not None:
            pending = db.get(Question, progress.last_question_id)
            if (
                pending is not None
                and pending.knowledge_point_id == kp.id
                and pending.set_no == set_no
                and pending.id not in excluded
            ):
                question = pending

        if question is None:
            answered = select(Attempt.question_id).where(Attempt.user_id == user.id)
            stmt = select(Question).where(
                Question.knowledge_point_id == kp.id,
                Question.set_no == set_no,
                Question.question_type != "pronunciation",
                Question.id.notin_(answered),
            )
            if excluded:
                stmt = stmt.where(Question.id.notin_(excluded))
            question = db.execute(stmt.order_by(func.random()).limit(1)).scalar_one_or_none()

        if question is not None:
            if progress is not None and progress.last_question_id != question.id:
                progress.last_question_id = question.id
                db.commit()

            total, done = _set_counts(db, user.id, kp.id, set_no)
            tiles = None
            if question.question_type == "spelling":
                tiles = tiles_service.tiles_for(question.id, str(question.answer))
            return QuestionNextResponse(
                question={
                    "id": str(question.id),
                    "question_type": question.question_type,
                    "stem": question.stem,
                    "options": question.options,
                    "knowledge_point_id": str(question.knowledge_point_id),
                    "tiles": tiles,
                },
                set_no=set_no,
                set_total=total,
                set_done=done,
                knowledge_point_name=kp.name,
            )

        # 这一套已经没有未答的题：记为完成，继续下一套
        if is_set_complete(db, user.id, kp.id, set_no):
            mark_set_complete(db, user, kp, set_no)
            db.commit()
            continue

        raise HTTPException(
            status_code=409,
            detail={"detail": "这一套没有可出的题", "code": "EMPTY_SET"},
        )

    raise HTTPException(
        status_code=409, detail={"detail": "没有可出的题", "code": "NO_QUESTION"}
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
            answer_text=answer_text(question) if question else None,
            word=word_payload(db, question) if question else None,
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

    progress = db.get(Progress, user.id)
    if progress is not None and progress.last_question_id == question.id:
        progress.last_question_id = None

    db.commit()

    return AnswerSubmitResponse(
        is_correct=correct,
        correct_answer=str(question.answer),
        progress_advanced=result["progress_advanced"],
        current_knowledge_point=_kp_payload(result["current_knowledge_point"]),
        new_badges=result["new_badges"],
        duplicated=False,
        answer_text=answer_text(question),
        word=word_payload(db, question),
    )
