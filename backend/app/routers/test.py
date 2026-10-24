import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import KnowledgePoint, Progress, Question, User
from ..schemas import TestAnswerRequest, TestAnswerResponse, TestQuestionOut, TestStartResponse
from ..services.attempts import first_kp_of_level
from ..services.judge import is_correct as judge_correct

router = APIRouter(prefix="/api/test", tags=["test"])

MAX_QUESTIONS = 10
UNCHANGED_LIMIT = 3
TEST_POOL_TYPES = ("letter", "word", "spelling", "listening")


@dataclass
class TestState:
    level: int
    answered: int = 0
    used_question_ids: set[str] = field(default_factory=set)
    last_level: int = 2
    unchanged_streak: int = 0


_test_sessions: dict[str, TestState] = {}


def _level_name(value: int) -> str:
    return f"L{value}"


def _finish_test(db: Session, user: User, state: TestState) -> str:
    """结算：写等级、落进度、记住测试出过的题（学习阶段优先避开）。"""
    level_name = _level_name(state.level)
    user.level = level_name
    user.has_tested = True

    first = first_kp_of_level(db, level_name)
    progress = db.get(Progress, user.id)
    if progress is None:
        progress = Progress(
            user_id=user.id,
            completed_knowledge_points=[],
            current_knowledge_point_id=None,
        )
        db.add(progress)

    progress.current_knowledge_point_id = first.id if first else None
    progress.last_question_id = None
    progress.test_seen_question_ids = list(state.used_question_ids)
    user.max_level = level_name

    db.commit()
    _test_sessions.pop(str(user.id), None)
    return level_name


def _pick_question(db: Session, state: TestState) -> Question | None:
    candidates = [state.level]
    if state.level > 1:
        candidates.append(state.level - 1)
    if state.level < 3:
        candidates.append(state.level + 1)

    used = [uuid.UUID(x) for x in state.used_question_ids]
    for difficulty in candidates:
        stmt = (
            select(Question)
            .where(
                Question.question_type.in_(TEST_POOL_TYPES),
                Question.difficulty == difficulty,
            )
            .order_by(func.random())
            .limit(1)
        )
        if used:
            stmt = stmt.where(Question.id.notin_(used))
        question = db.execute(stmt).scalar_one_or_none()
        if question is not None:
            return question
    return None


@router.post("/start", response_model=TestStartResponse)
def start_test(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.has_tested:
        raise HTTPException(
            status_code=409, detail={"detail": "已完成水平测试", "code": "ALREADY_TESTED"}
        )

    state = TestState(level=2, last_level=2)
    question = _pick_question(db, state)
    if question is None:
        raise HTTPException(
            status_code=409, detail={"detail": "题库为空", "code": "EMPTY_QUESTION_BANK"}
        )

    state.used_question_ids.add(str(question.id))
    _test_sessions[str(user.id)] = state

    return TestStartResponse(
        question=TestQuestionOut(
            id=str(question.id),
            question_type=question.question_type,
            stem=question.stem,
            options=question.options,
        ),
        question_index=1,
    )


@router.post("/answer", response_model=TestAnswerResponse)
def answer_test(
    payload: TestAnswerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    state = _test_sessions.get(str(user.id))
    if state is None:
        raise HTTPException(
            status_code=409, detail={"detail": "测试未开始", "code": "TEST_NOT_STARTED"}
        )

    try:
        question_id = uuid.UUID(payload.question_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="question_id 非法")

    if str(question_id) not in state.used_question_ids:
        raise HTTPException(status_code=409, detail={"detail": "题目不属于本次测试", "code": "BAD_QUESTION"})

    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    correct = judge_correct(question, payload.answer)
    state.answered += 1

    previous = state.level
    if correct:
        state.level = min(3, state.level + 1)
    else:
        state.level = max(1, state.level - 1)

    if state.level == previous:
        state.unchanged_streak += 1
    else:
        state.unchanged_streak = 0
    state.last_level = state.level

    finished = state.answered >= MAX_QUESTIONS or state.unchanged_streak >= UNCHANGED_LIMIT

    if finished:
        level_name = _finish_test(db, user, state)
        return TestAnswerResponse(is_finished=True, next_question=None, level=level_name)

    next_question = _pick_question(db, state)
    if next_question is None:
        level_name = _finish_test(db, user, state)
        return TestAnswerResponse(is_finished=True, next_question=None, level=level_name)

    state.used_question_ids.add(str(next_question.id))
    db.commit()

    return TestAnswerResponse(
        is_finished=False,
        next_question=TestQuestionOut(
            id=str(next_question.id),
            question_type=next_question.question_type,
            stem=next_question.stem,
            options=next_question.options,
        ),
        level=None,
    )
