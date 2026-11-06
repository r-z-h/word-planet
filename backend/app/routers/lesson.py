import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Progress, Question, QuestionFlower, SetProgress, User
from ..schemas import (
    KpProgressOut,
    LessonOverview,
    MapPlanetOut,
    MapResponse,
    PlanetSetOut,
    PlanetSetsResponse,
    SelectKpRequest,
    SwitchLevelRequest,
)
from ..services import rewards
from ..services.attempts import local_date_of, local_today
from ..services.lesson import (
    LEVELS,
    SETS_REQUIRED,
    current_set_no,
    kp_set_numbers,
    level_gate,
    level_kps,
    next_level,
    set_summary,
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
        required_medals=0,
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


@router.get("/map", response_model=MapResponse)
def map_overview(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    """星球地图：7 个星球 + 进度 / 徽记 / 锁定 / 纯练完成状态。"""
    max_level = _max_level(user)
    idx = {lv: i for i, lv in enumerate(LEVELS)}
    progress = db.get(Progress, user.id)
    current_id = (
        str(progress.current_knowledge_point_id)
        if progress and progress.current_knowledge_point_id
        else None
    )

    planets: list[MapPlanetOut] = []
    for lv in LEVELS:
        for kp in level_kps(db, lv):
            s = set_summary(db, user.id, kp)
            pure = not kp.produces_flowers
            is_complete = False
            if pure:
                hit = db.execute(
                    select(SetProgress.id)
                    .where(
                        SetProgress.user_id == user.id,
                        SetProgress.knowledge_point_id == kp.id,
                        SetProgress.is_complete.is_(True),
                    )
                    .limit(1)
                ).first()
                is_complete = hit is not None
            planets.append(
                MapPlanetOut(
                    id=str(kp.id),
                    name=kp.name,
                    level=kp.level,
                    question_type=kp.question_type,
                    total_sets=s["total_sets"],
                    completed_sets=s["completed_sets"],
                    current_set=s["current_set"],
                    medals=s["medals"],
                    max_medals=s["total_sets"],
                    mastered_sets=s["mastered_sets"],
                    pure=pure,
                    counts_for_gate=kp.counts_for_gate,
                    is_complete=is_complete,
                    gate_mode=kp.gate_mode,
                    gate_required=kp.gate_required,
                    medal_name=kp.medal_name,
                    medal_icon=kp.medal_icon,
                    produces_flowers=kp.produces_flowers,
                    completed=s["completed"],
                    locked=idx[kp.level] > idx[max_level],
                    is_current=(str(kp.id) == current_id),
                )
            )

    today = local_today(db)
    today_flowers = db.execute(
        select(func.count())
        .select_from(QuestionFlower)
        .where(
            QuestionFlower.user_id == user.id,
            local_date_of(QuestionFlower.earned_at) == today,
        )
    ).scalar_one()

    # 今日做题 / 正确 / 最高连击（按作答时间顺序算）
    today_attempts = db.execute(
        select(func.count())
        .select_from(Attempt)
        .where(
            Attempt.user_id == user.id,
            Attempt.question_type != "practice",
            local_date_of(Attempt.created_at) == today,
        )
    ).scalar_one()
    today_correct = db.execute(
        select(func.count())
        .select_from(Attempt)
        .where(
            Attempt.user_id == user.id,
            Attempt.is_correct.is_(True),
            Attempt.question_type != "practice",
            local_date_of(Attempt.created_at) == today,
        )
    ).scalar_one()
    seq = db.execute(
        select(Attempt.is_correct)
        .where(
            Attempt.user_id == user.id,
            Attempt.question_type != "practice",
            local_date_of(Attempt.created_at) == today,
        )
        .order_by(Attempt.created_at)
    ).scalars()
    best = cur = 0
    for ok in seq:
        cur = cur + 1 if ok else 0
        best = max(best, cur)

    # 本周一→周日 每天作答数
    monday = today - timedelta(days=today.weekday())
    week_counts = []
    for i in range(7):
        d = monday + timedelta(days=i)
        n = db.execute(
            select(func.count())
            .select_from(Attempt)
            .where(
                Attempt.user_id == user.id,
                Attempt.question_type != "practice",
                local_date_of(Attempt.created_at) == d,
            )
        ).scalar_one()
        week_counts.append(int(n))

    gate = level_gate(db, user)

    total_flowers = db.execute(
        select(func.count()).select_from(QuestionFlower).where(QuestionFlower.user_id == user.id)
    ).scalar_one()

    return MapResponse(
        level=user.level,
        max_level=max_level,
        current_planet_id=current_id,
        planets=planets,
        today_flowers=int(today_flowers),
        today_stars=rewards.stars_exchanged_on(db, user.id, today),
        total_flowers=int(total_flowers),
        today_attempts=int(today_attempts),
        today_correct=int(today_correct),
        today_max_combo=int(best),
        week_counts=week_counts,
        gate_ready=bool(gate["ready"]),
        next_level=next_level(user.level),
    )


@router.get("/planet-sets", response_model=PlanetSetsResponse)
def planet_sets(
    knowledge_point_id: str,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """当前星球各套明细（含未开始），供首页「兑换」抽屉使用。"""
    try:
        kp_id = uuid.UUID(knowledge_point_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="knowledge_point_id 非法")
    kp = db.get(KnowledgePoint, kp_id)
    if kp is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    if kp.level != user.level:
        raise HTTPException(
            status_code=409,
            detail={"detail": "该星球不属于当前等级", "code": "LEVEL_MISMATCH"},
        )

    all_sets = kp_set_numbers(db, kp.id)
    current = current_set_no(db, user.id, kp.id)
    sp_map = {
        sp.set_no: sp
        for sp in db.execute(
            select(SetProgress).where(
                SetProgress.user_id == user.id,
                SetProgress.knowledge_point_id == kp.id,
            )
        ).scalars()
    }
    sets = []
    for set_no in all_sets:
        sp = sp_map.get(set_no)
        total = db.execute(
            select(func.count())
            .select_from(Question)
            .where(Question.knowledge_point_id == kp.id, Question.set_no == set_no)
        ).scalar_one()
        fl = rewards.count_flowers(db, user.id, kp.id, set_no)
        stars = (sp.stars_earned or 0) if sp else 0
        medals = (sp.medals_granted or 0) if sp else 0
        if sp is not None:
            status = "completed"
        elif set_no == current:
            status = "in_progress"
        else:
            status = "not_started"
        sets.append(
            PlanetSetOut(
                set_no=set_no,
                total_count=int(total),
                flowers=fl,
                stars=int(stars),
                medals_granted=int(medals),
                exchangeable_stars=rewards.exchangeable_stars_for(fl, int(stars)),
                can_exchange_medal=rewards.can_exchange_medal_for(int(stars), int(medals)),
                is_complete=bool(
                    total
                    and (fl >= total or (sp is not None and (sp.correct_count or 0) >= total))
                ),
                status=status,
                is_current=(set_no == current),
            )
        )
    return PlanetSetsResponse(
        knowledge_point_id=str(kp.id),
        name=kp.name,
        level=kp.level,
        total_sets=len(all_sets),
        medals=rewards.planet_medal_count(db, user.id, kp.id),
        mastered_sets=sum(1 for x in sets if x.is_complete),
        sets=sets,
    )
