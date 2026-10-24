import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import KnowledgePoint, Progress, User
from ..schemas import KpProgressOut, LessonOverview, SelectKpRequest, SwitchLevelRequest
from ..services.lesson import (
    LEVELS,
    SETS_REQUIRED,
    level_gate,
    level_kps,
    next_level,
)

router = APIRouter(prefix="/api/lesson", tags=["lesson"])


def _kp_out(kp: KnowledgePoint) -> dict:
    return {
        "id": str(kp.id),
        "level": kp.level,
        "name": kp.name,
        "question_type": kp.question_type,
    }


def _max_level(user: User) -> str:
    return user.max_level or user.level or "L1"


@router.get("/overview", response_model=LessonOverview)
def overview(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    gate = level_gate(db, user)
    max_level = _max_level(user)

    switchable = [
        lv for lv in LEVELS if LEVELS.index(lv) <= LEVELS.index(max_level)
    ]

    return LessonOverview(
        level=user.level,
        max_level=max_level,
        required_sets=SETS_REQUIRED,
        knowledge_points=[KpProgressOut(**item) for item in gate["knowledge_points"]],
        gate_ready=gate["ready"],
        can_test=gate["ready"] and next_level(user.level) is not None,
        next_level=next_level(user.level),
        switchable_levels=switchable,
    )


@router.post("/select")
def select_knowledge_point(
    payload: SelectKpRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    try:
        kp_id = uuid.UUID(payload.knowledge_point_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="knowledge_point_id 非法")

    kp = db.get(KnowledgePoint, kp_id)
    if kp is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    if kp.level != user.level:
        raise HTTPException(
            status_code=409,
            detail={"detail": "该知识点不属于当前等级", "code": "LEVEL_MISMATCH"},
        )

    progress = db.get(Progress, user.id)
    if progress is None:
        progress = Progress(user_id=user.id, completed_knowledge_points=[])
        db.add(progress)
    progress.current_knowledge_point_id = kp.id
    progress.last_question_id = None
    db.commit()

    return {"ok": True, "knowledge_point": _kp_out(kp)}


@router.post("/switch-level")
def switch_level(
    payload: SwitchLevelRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    if payload.level not in LEVELS:
        raise HTTPException(status_code=422, detail="等级非法")

    max_level = _max_level(user)
    if LEVELS.index(payload.level) > LEVELS.index(max_level):
        raise HTTPException(
            status_code=409,
            detail={"detail": "还没有解锁这个等级", "code": "LEVEL_LOCKED"},
        )

    kps = level_kps(db, payload.level)
    if not kps:
        raise HTTPException(status_code=409, detail="该等级没有知识点")

    user.level = payload.level

    progress = db.get(Progress, user.id)
    if progress is None:
        progress = Progress(user_id=user.id, completed_knowledge_points=[])
        db.add(progress)
    progress.current_knowledge_point_id = kps[0].id
    progress.last_question_id = None
    db.commit()

    return {
        "ok": True,
        "level": user.level,
        "max_level": _max_level(user),
        "knowledge_point": _kp_out(kps[0]),
    }
