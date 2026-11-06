"""按「套」推进学习：当前套计算、套完成、升级门槛。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Attempt, KnowledgePoint, Progress, Question, SetProgress, User
from . import rewards

SETS_REQUIRED = 3  # 每套/若干套的展示统计口径
LEVELS = ["L1", "L2", "L3"]


def level_kps(db: Session, level: str) -> list[KnowledgePoint]:
    return list(
        db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.level == level)
            .order_by(KnowledgePoint.sort_order)
        ).scalars()
    )


def kp_set_numbers(db: Session, kp_id: uuid.UUID) -> list[int]:
    rows = db.execute(
        select(Question.set_no).where(Question.knowledge_point_id == kp_id).distinct()
    ).scalars()
    return sorted(rows)


def completed_set_numbers(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID) -> set[int]:
    rows = db.execute(
        select(SetProgress.set_no).where(
            SetProgress.user_id == user_id, SetProgress.knowledge_point_id == kp_id
        )
    ).scalars()
    return set(rows)


def current_set_no(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID) -> int | None:
    """还没做完的第一套；全部做完则返回 None。"""
    all_sets = kp_set_numbers(db, kp_id)
    done = completed_set_numbers(db, user_id, kp_id)
    for set_no in all_sets:
        if set_no not in done:
            return set_no
    return None


def is_set_complete(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID, set_no: int) -> bool:
    """这一套的每一道题都被作答过（对错不论）即算完成。"""
    qids = db.execute(
        select(Question.id).where(
            Question.knowledge_point_id == kp_id, Question.set_no == set_no
        )
    ).scalars().all()
    if not qids:
        return False
    attempted = db.execute(
        select(func.count(func.distinct(Attempt.question_id))).where(
            Attempt.user_id == user_id,
            Attempt.question_id.in_(qids),
            Attempt.question_type != "practice",
        )
    ).scalar_one()
    return attempted >= len(qids)


def mark_set_complete(db: Session, user: User, kp: KnowledgePoint, set_no: int) -> None:
    exists = db.execute(
        select(SetProgress).where(
            SetProgress.user_id == user.id,
            SetProgress.knowledge_point_id == kp.id,
            SetProgress.set_no == set_no,
        )
    ).scalar_one_or_none()
    if exists is not None:
        return

    qids = select(Question.id).where(
        Question.knowledge_point_id == kp.id, Question.set_no == set_no
    )
    total = db.execute(select(func.count()).select_from(Question).where(
        Question.knowledge_point_id == kp.id, Question.set_no == set_no
    )).scalar_one()
    correct = db.execute(
        select(func.count(func.distinct(Attempt.question_id))).where(
            Attempt.user_id == user.id,
            Attempt.is_correct.is_(True),
            Attempt.question_id.in_(qids),
            Attempt.question_type != "practice",
        )
    ).scalar_one()

    db.add(
        SetProgress(
            user_id=user.id,
            knowledge_point_id=kp.id,
            set_no=set_no,
            correct_count=correct,
            total_count=total,
        )
    )
    db.flush()


def kp_completed(db: Session, user_id: uuid.UUID, kp: KnowledgePoint) -> bool:
    """该知识点是否"已完成"：全部题目都答对过（主流程，不含练习）。字母表用这个判定。"""
    qids = db.execute(
        select(Question.id).where(Question.knowledge_point_id == kp.id)
    ).scalars().all()
    if not qids:
        return False
    correct = db.execute(
        select(func.count(func.distinct(Attempt.question_id))).where(
            Attempt.user_id == user_id,
            Attempt.is_correct.is_(True),
            Attempt.question_type != "practice",
            Attempt.question_id.in_(qids),
        )
    ).scalar_one()
    return correct >= len(qids)


def set_summary(db: Session, user_id: uuid.UUID, kp: KnowledgePoint) -> dict:
    all_sets = kp_set_numbers(db, kp.id)
    done = completed_set_numbers(db, user_id, kp.id)
    medals = int(rewards.planet_medal_count(db, user_id, kp.id))
    mastered = db.execute(
        select(func.count())
        .select_from(SetProgress)
        .where(
            SetProgress.user_id == user_id,
            SetProgress.knowledge_point_id == kp.id,
            SetProgress.is_complete.is_(True),
        )
    ).scalar_one()
    completed = kp_completed(db, user_id, kp) if kp.gate_mode == "completion" else False
    if kp.gate_mode == "completion":
        meets = completed
    else:
        meets = medals >= int(kp.gate_required)
    return {
        "total_sets": len(all_sets),
        "completed_sets": len(done),
        "current_set": current_set_no(db, user_id, kp.id),
        "medals": medals,
        "mastered_sets": int(mastered),
        "completed": completed,
        # 门槛：completion 看完成；medals 看已兑换徽记数 >= 该星球要求
        "meets_gate": meets,
    }


def resolve_current_kp(db: Session, user: User) -> KnowledgePoint | None:
    progress = db.get(Progress, user.id)
    if progress and progress.current_knowledge_point_id:
        kp = db.get(KnowledgePoint, progress.current_knowledge_point_id)
        if kp is not None and kp.level == user.level:
            return kp
    # 当前知识点丢失或不属于当前等级：落到本级第一个
    kps = level_kps(db, user.level) if user.level else []
    if not kps:
        return None
    if progress is None:
        progress = Progress(user_id=user.id, completed_knowledge_points=[])
        db.add(progress)
    progress.current_knowledge_point_id = kps[0].id
    db.commit()
    return kps[0]


def level_gate(db: Session, user: User) -> dict:
    """本级升级门槛：按每个星球的配置分别判定（徽记数 >= 各自要求，或"完成"）。"""
    kps = level_kps(db, user.level) if user.level else []
    items = []
    ready = True
    for kp in kps:
        s = set_summary(db, user.id, kp)
        counted = kp.counts_for_gate
        if counted and not s["meets_gate"]:
            ready = False
        items.append(
            {
                "id": str(kp.id),
                "name": kp.name,
                "question_type": kp.question_type,
                "counts_for_gate": counted,
                "gate_mode": kp.gate_mode,
                "gate_required": kp.gate_required,
                "medal_name": kp.medal_name,
                "medal_icon": kp.medal_icon,
                "produces_flowers": kp.produces_flowers,
                **s,
            }
        )
    return {
        "level": user.level,
        "required_sets": SETS_REQUIRED,
        "ready": ready and bool(kps),
        "knowledge_points": items,
    }


def next_level(level: str | None) -> str | None:
    if level not in LEVELS:
        return None
    idx = LEVELS.index(level)
    return LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
