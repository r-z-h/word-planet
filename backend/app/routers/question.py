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

    progress = db.get(Progress, user.id)
    question = None

    # 主流程只过一遍：答过的题（无论对错）不再出现，答错的只进错题本
    answered = select(Attempt.question_id).where(Attempt.user_id == user.id)

    # 1) 恢复上次未作答的那道题（中途退出后重新进来要看到同一题）
    if progress is not None and progress.last_question_id is not None:
        pending = db.get(Question, progress.last_question_id)
        if (
            pending is not None
            and pending.knowledge_point_id == kp.id
            and pending.question_type != "pronunciation"
        ):
            question = pending

    # 2) 当前知识点没做过的题（优先跳过水平测试里已经出过的）
    if question is None:
        seen_in_test = {uuid.UUID(x) for x in (progress.test_seen_question_ids or [])}
        stmt = _base_pool(kp.id).where(Question.id.notin_(answered))
        if seen_in_test:
            stmt = stmt.where(Question.id.notin_(seen_in_test))
        question = db.execute(stmt.order_by(func.random()).limit(1)).scalar_one_or_none()

    # 3) 上面被测试题挤空时，允许出“测试出过但没做过”的题，
    #    否则该知识点会因为凑不满题目数而永远无法完成
    if question is None:
        question = db.execute(
            _base_pool(kp.id)
            .where(Question.id.notin_(answered))
            .order_by(func.random())
            .limit(1)
        ).scalar_one_or_none()

    # 4) 兜底：本知识点全部做过时允许重复（正常不会走到，做完就会推进）
    if question is None:
        question = db.execute(_base_pool(kp.id).order_by(func.random()).limit(1)).scalar_one_or_none()

    if question is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "当前知识点没有题目", "code": "EMPTY_KNOWLEDGE_POINT"},
        )

    if progress is not None and progress.last_question_id != question.id:
        progress.last_question_id = question.id
        db.commit()

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
    )
