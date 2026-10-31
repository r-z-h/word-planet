"""三层奖励记账：花 → 星 → 徽记。

定位：**纯记账服务**。只负责写 `question_flowers`、重算 `set_progress` 缓存、
以及计算/执行兑换；**不改动任何现有答题接口的行为**。接口层将来接入时直接调用这里
（见 `docs/玩法设计.md` 第 9 章 / `docs/游戏设计.md` 14.1）。

口径（与 游戏设计.md 一致）：
- 答对 1 题 = 1 朵花（按题记账，`UNIQUE(user_id, question_id)` 每题只记一次）
- 3 朵花 = 1 颗星（手动兑换）
- 5 颗星 = 1 个徽记（手动兑换，每套最多 1 个）
- 可兑星数 = (flowers_earned - stars_earned*3) // 3
- 可兑徽记 = stars_earned - medals_granted*5 >= 5
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Attempt,
    FlowerExchange,
    PlanetMedal,
    Question,
    QuestionFlower,
    SetProgress,
)

FLOWERS_PER_STAR = 3
STARS_PER_MEDAL = 5


# ---------------------------------------------------------------- 内部工具

def _set_question_ids(db: Session, kp_id: uuid.UUID, set_no: int) -> list[uuid.UUID]:
    return list(
        db.execute(
            select(Question.id).where(
                Question.knowledge_point_id == kp_id, Question.set_no == set_no
            )
        ).scalars()
    )


def get_set_progress(
    db: Session, user_id: uuid.UUID, kp_id: uuid.UUID, set_no: int
) -> SetProgress | None:
    return db.execute(
        select(SetProgress).where(
            SetProgress.user_id == user_id,
            SetProgress.knowledge_point_id == kp_id,
            SetProgress.set_no == set_no,
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------- 记账

def award_flower(
    db: Session,
    user_id: uuid.UUID,
    question: Question,
    *,
    source: str = "main",
) -> bool:
    """给一道题记一朵花。已记过返回 False（幂等）。不 commit，由调用方决定事务边界。"""
    if source not in ("main", "practice"):
        raise ValueError("source 只能是 'main' 或 'practice'")

    exists = db.execute(
        select(QuestionFlower.id).where(
            QuestionFlower.user_id == user_id,
            QuestionFlower.question_id == question.id,
        )
    ).scalar_one_or_none()
    if exists is not None:
        return False

    db.add(
        QuestionFlower(
            user_id=user_id,
            question_id=question.id,
            set_no=question.set_no,
            source=source,
        )
    )
    db.flush()
    recompute_set_progress(db, user_id, question.knowledge_point_id, question.set_no)
    return True


def recompute_set_progress(
    db: Session, user_id: uuid.UUID, kp_id: uuid.UUID, set_no: int
) -> SetProgress | None:
    """按 `question_flowers` 重算该套的 flowers_earned，并按「全部答对」更新 is_complete。

    - 只在 `set_progress` 行**已存在**时更新（不新建）：新建行会被
      `completed_set_numbers` 误判成「这一套已完成」。
    - `flowers_earned` 只增不减（取 max）
    - `is_complete` = 该套所有题都「答对过至少一次」（纯练星球也用它）
    """
    sp = get_set_progress(db, user_id, kp_id, set_no)
    if sp is None:
        return None

    qids = _set_question_ids(db, kp_id, set_no)
    total = len(qids)

    flowers = 0
    if qids:
        flowers = db.execute(
            select(func.count())
            .select_from(QuestionFlower)
            .where(
                QuestionFlower.user_id == user_id,
                QuestionFlower.question_id.in_(qids),
            )
        ).scalar_one()
    sp.flowers_earned = max(sp.flowers_earned or 0, int(flowers))

    if qids:
        correct = db.execute(
            select(func.count(func.distinct(Attempt.question_id))).where(
                Attempt.user_id == user_id,
                Attempt.is_correct.is_(True),
                Attempt.question_type != "practice",
                Attempt.question_id.in_(qids),
            )
        ).scalar_one()
        if correct >= total:
            sp.is_complete = True

    db.flush()
    return sp


def count_flowers(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID, set_no: int) -> int:
    """该套当前已记了多少朵花（直接数账本，套未完成时也能用）。"""
    qids = _set_question_ids(db, kp_id, set_no)
    if not qids:
        return 0
    return int(
        db.execute(
            select(func.count())
            .select_from(QuestionFlower)
            .where(
                QuestionFlower.user_id == user_id,
                QuestionFlower.question_id.in_(qids),
            )
        ).scalar_one()
    )


def exchangeable_stars_for(flowers: int, stars: int) -> int:
    return max(0, (flowers - stars * FLOWERS_PER_STAR) // FLOWERS_PER_STAR)


def can_exchange_medal_for(stars: int, medals_granted: int) -> bool:
    return (stars - medals_granted * STARS_PER_MEDAL) >= STARS_PER_MEDAL


# ---------------------------------------------------------------- 可兑计算

def exchangeable_stars(sp: SetProgress) -> int:
    """该套当前还能兑出几颗星。"""
    return exchangeable_stars_for(sp.flowers_earned or 0, sp.stars_earned or 0)


def can_exchange_medal(sp: SetProgress) -> bool:
    """该套当前是否够兑 1 个徽记。"""
    return can_exchange_medal_for(sp.stars_earned or 0, sp.medals_granted or 0)


def planet_medal_count(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID) -> int:
    row = db.execute(
        select(PlanetMedal).where(
            PlanetMedal.user_id == user_id, PlanetMedal.knowledge_point_id == kp_id
        )
    ).scalar_one_or_none()
    return int(row.medals) if row else 0


def _bump_planet_medal(
    db: Session, user_id: uuid.UUID, kp_id: uuid.UUID, amount: int
) -> PlanetMedal:
    row = db.execute(
        select(PlanetMedal).where(
            PlanetMedal.user_id == user_id, PlanetMedal.knowledge_point_id == kp_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = PlanetMedal(user_id=user_id, knowledge_point_id=kp_id, medals=0)
        db.add(row)
        db.flush()
    row.medals = (row.medals or 0) + amount
    row.updated_at = func.now()
    db.flush()
    return row


# ---------------------------------------------------------------- 兑换

def _existing_exchange(db: Session, user_id: uuid.UUID, key: str | None) -> FlowerExchange | None:
    if not key:
        return None
    return db.execute(
        select(FlowerExchange).where(
            FlowerExchange.user_id == user_id, FlowerExchange.idempotency_key == key
        )
    ).scalar_one_or_none()


def exchange_flowers_to_stars(
    db: Session,
    user_id: uuid.UUID,
    kp_id: uuid.UUID,
    set_no: int,
    amount: int = 1,
    *,
    idempotency_key: str | None = None,
) -> SetProgress:
    """花 → 星。amount 为兑换次数（1 次 = 消耗 3 朵花换 1 颗星）。不 commit。

    带 idempotency_key 时：同一 key 重复调用直接返回当前进度，不重复扣。
    """
    if amount < 1:
        raise ValueError("amount 必须 >= 1")
    sp = get_set_progress(db, user_id, kp_id, set_no)
    if sp is None:
        raise ValueError("该套没有进度记录，无法兑换")
    if _existing_exchange(db, user_id, idempotency_key) is not None:
        return sp  # 幂等：已处理过

    available = exchangeable_stars(sp)
    if amount > available:
        raise ValueError(f"可兑星数不足：可兑 {available}，请求 {amount}")

    sp.stars_earned = (sp.stars_earned or 0) + amount
    db.add(
        FlowerExchange(
            user_id=user_id,
            from_kind="flower",
            to_kind="star",
            set_no=set_no,
            knowledge_point_id=kp_id,
            amount=amount,
            idempotency_key=idempotency_key,
        )
    )
    db.flush()
    return sp


def exchange_stars_to_medal(
    db: Session,
    user_id: uuid.UUID,
    kp_id: uuid.UUID,
    set_no: int,
    amount: int = 1,
    *,
    idempotency_key: str | None = None,
) -> SetProgress:
    """星 → 徽记。一整套最多产出 1 个徽记。不 commit。带 idempotency_key 时幂等。"""
    if amount < 1:
        raise ValueError("amount 必须 >= 1")
    sp = get_set_progress(db, user_id, kp_id, set_no)
    if sp is None:
        raise ValueError("该套没有进度记录，无法兑换")
    if _existing_exchange(db, user_id, idempotency_key) is not None:
        return sp  # 幂等：已处理过

    if (sp.medals_granted or 0) + amount > 1:
        raise ValueError("每套最多只能产出 1 个徽记")
    if not can_exchange_medal(sp):
        raise ValueError("星数不足，兑不出徽记")

    sp.medals_granted = (sp.medals_granted or 0) + amount
    db.add(
        FlowerExchange(
            user_id=user_id,
            from_kind="star",
            to_kind="medal",
            set_no=set_no,
            knowledge_point_id=kp_id,
            amount=amount,
            idempotency_key=idempotency_key,
        )
    )
    _bump_planet_medal(db, user_id, kp_id, amount)
    db.flush()
    return sp


# ---------------------------------------------------------------- 每日口径

def stars_exchanged_on(db: Session, user_id: uuid.UUID, day: date) -> int:
    """某天「兑换出的星星数」（今日星口径）。"""
    total = db.execute(
        select(func.coalesce(func.sum(FlowerExchange.amount), 0)).where(
            FlowerExchange.user_id == user_id,
            FlowerExchange.to_kind == "star",
            func.date(FlowerExchange.created_at) == day,
        )
    ).scalar_one()
    return int(total)
