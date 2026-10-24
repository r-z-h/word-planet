"""本级能力测试：门槛校验、10 题对决、通过后解锁并让用户选择升级/留级。"""

import random
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import KnowledgePoint, LevelTest, Progress, Question, User
from ..schemas import (
    LevelTestAnswerRequest,
    LevelTestAnswerResponse,
    LevelTestChooseRequest,
    LevelTestChooseResponse,
    LevelTestStartResponse,
    TestQuestionOut,
)
from ..services.judge import is_correct as judge_correct
from ..services.lesson import LEVELS, SETS_REQUIRED, level_gate, level_kps, next_level

router = APIRouter(prefix="/api/level-test", tags=["level-test"])

QUESTION_COUNT = 10
PASS_SCORE = 8

# user_id -> {"level", "question_ids", "answers", "index", "score"}
_sessions: dict[str, dict] = {}


def _gate(user: User, db: Session) -> dict:
    return level_gate(db, user)


@router.get("/status")
def status(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    gate = _gate(user, db)
    nxt = next_level(user.level)

    last = db.execute(
        select(LevelTest)
        .where(LevelTest.user_id == user.id)
        .order_by(LevelTest.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    count = db.execute(
        select(func.count()).select_from(LevelTest).where(LevelTest.user_id == user.id)
    ).scalar_one()

    return {
        "level": user.level,
        "next_level": nxt,
        "required_sets": SETS_REQUIRED,
        "gate_ready": gate["ready"],
        "can_test": gate["ready"] and nxt is not None,
        "attempt_count": count,
        "last_result": (
            {
                "score": last.score,
                "total": last.total,
                "passed": last.passed,
                "at": last.created_at,
            }
            if last
            else None
        ),
    }


@router.post("/start", response_model=LevelTestStartResponse)
def start(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    gate = _gate(user, db)
    if not gate["ready"]:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"本级每个知识点至少完成 {SETS_REQUIRED} 套后才能测试",
                "code": "GATE_NOT_READY",
            },
        )

    nxt = next_level(user.level)
    if nxt is None:
        raise HTTPException(
            status_code=409, detail={"detail": "已经是最高等级", "code": "MAX_LEVEL"}
        )

    pool = list(
        db.execute(
            select(Question)
            .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
            .where(
                KnowledgePoint.level == user.level,
                Question.question_type != "pronunciation",
            )
        ).scalars()
    )
    if len(pool) < QUESTION_COUNT:
        raise HTTPException(
            status_code=409, detail={"detail": "本级题库不足", "code": "NOT_ENOUGH_QUESTIONS"}
        )

    picked = random.sample(pool, QUESTION_COUNT)
    state = {
        "level": user.level,
        "question_ids": [str(q.id) for q in picked],
        "answers": {},
        "index": 0,
        "score": 0,
    }
    _sessions[str(user.id)] = state

    first = picked[0]
    return LevelTestStartResponse(
        question=TestQuestionOut(
            id=str(first.id),
            question_type=first.question_type,
            stem=first.stem,
            options=first.options,
        ),
        index=1,
    )


@router.post("/answer", response_model=LevelTestAnswerResponse)
def answer(
    payload: LevelTestAnswerRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    state = _sessions.get(str(user.id))
    if state is None:
        raise HTTPException(
            status_code=409, detail={"detail": "测试未开始", "code": "TEST_NOT_STARTED"}
        )

    if payload.question_id not in state["question_ids"]:
        raise HTTPException(
            status_code=409, detail={"detail": "题目不属于本次测试", "code": "BAD_QUESTION"}
        )

    question = db.get(Question, uuid.UUID(payload.question_id))
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    if judge_correct(question, payload.answer):
        state["score"] += 1

    state["index"] += 1

    if state["index"] >= QUESTION_COUNT:
        score = state["score"]
        passed = score >= PASS_SCORE
        nxt = next_level(user.level)

        db.add(
            LevelTest(
                user_id=user.id,
                level=user.level,
                score=score,
                total=QUESTION_COUNT,
                passed=passed,
            )
        )
        if passed and nxt is not None:
            # 解锁下一级，但先不改 level —— 由用户选择升级还是留级
            current_max = user.max_level or user.level
            if current_max is None or LEVELS.index(nxt) > LEVELS.index(current_max):
                user.max_level = nxt
        db.commit()
        _sessions.pop(str(user.id), None)

        return LevelTestAnswerResponse(
            is_finished=True,
            score=score,
            total=QUESTION_COUNT,
            passed=passed,
            next_level=nxt,
        )

    next_id = state["question_ids"][state["index"]]
    q = db.get(Question, uuid.UUID(next_id))
    return LevelTestAnswerResponse(
        is_finished=False,
        score=state["score"],
        total=QUESTION_COUNT,
        next_level=None,
    )


@router.get("/next")
def next_question(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    state = _sessions.get(str(user.id))
    if state is None:
        raise HTTPException(
            status_code=409, detail={"detail": "测试未开始", "code": "TEST_NOT_STARTED"}
        )
    if state["index"] >= QUESTION_COUNT:
        raise HTTPException(
            status_code=409, detail={"detail": "测试已结束", "code": "TEST_FINISHED"}
        )
    q = db.get(Question, uuid.UUID(state["question_ids"][state["index"]]))
    return {
        "question": {
            "id": str(q.id),
            "question_type": q.question_type,
            "stem": q.stem,
            "options": q.options,
        },
        "index": state["index"] + 1,
    }


@router.post("/choose", response_model=LevelTestChooseResponse)
def choose(
    payload: LevelTestChooseRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    nxt = next_level(user.level)
    max_level = user.max_level or user.level

    if payload.go_next:
        if nxt is None:
            raise HTTPException(status_code=409, detail="已经是最高等级")
        if LEVELS.index(nxt) > LEVELS.index(max_level):
            raise HTTPException(
                status_code=409,
                detail={"detail": "还没有通过本级测试", "code": "NOT_UNLOCKED"},
            )
        kps = level_kps(db, nxt)
        if not kps:
            raise HTTPException(status_code=409, detail="该等级没有知识点")
        user.level = nxt
        progress = db.get(Progress, user.id)
        if progress is None:
            progress = Progress(user_id=user.id, completed_knowledge_points=[])
            db.add(progress)
        progress.current_knowledge_point_id = kps[0].id
        progress.last_question_id = None
        db.commit()
        return LevelTestChooseResponse(
            level=user.level,
            max_level=user.max_level or user.level,
            knowledge_point={
                "id": str(kps[0].id),
                "level": kps[0].level,
                "name": kps[0].name,
                "question_type": kps[0].question_type,
            },
        )

    db.commit()
    progress = db.get(Progress, user.id)
    kp = (
        db.get(KnowledgePoint, progress.current_knowledge_point_id)
        if progress and progress.current_knowledge_point_id
        else None
    )
    return LevelTestChooseResponse(
        level=user.level,
        max_level=max_level,
        knowledge_point=(
            {
                "id": str(kp.id),
                "level": kp.level,
                "name": kp.name,
                "question_type": kp.question_type,
            }
            if kp
            else None
        ),
    )
