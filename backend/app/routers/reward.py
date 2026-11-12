"""三层奖励接口：查询本套花/星/徽记、手动兑换。

口径见 `docs/游戏设计.md` 14.1 与 `docs/玩法设计.md` 第 9 章。
记账逻辑全在 `services/rewards.py`，这里只做参数解析与错误映射。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import FlowerExchange, KnowledgePoint, User
from ..schemas import (
    RewardExchangeHistoryItem,
    RewardExchangeHistoryOut,
    RewardExchangeRequest,
    RewardExchangeResponse,
    RewardSummaryOut,
)
from ..services import rewards
from ..services.lesson import current_set_no, resolve_current_kp

router = APIRouter(prefix="/api/reward", tags=["reward"])


def _resolve(db: Session, user: User, kp_id: str | None, set_no: int | None) -> tuple[KnowledgePoint, int]:
    if kp_id:
        try:
            kp = db.get(KnowledgePoint, uuid.UUID(kp_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="knowledge_point_id 非法")
        if kp is None:
            raise HTTPException(status_code=404, detail="知识点不存在")
    else:
        kp = resolve_current_kp(db, user)
        if kp is None:
            raise HTTPException(
                status_code=409,
                detail={"detail": "没有当前知识点", "code": "NO_CURRENT_KNOWLEDGE_POINT"},
            )

    if set_no is None:
        set_no = current_set_no(db, user.id, kp.id)
        if set_no is None:
            raise HTTPException(
                status_code=409,
                detail={"detail": "该知识点已全部完成，没有进行中的套", "code": "NO_CURRENT_SET"},
            )
    return kp, set_no


def _summary(db: Session, user: User, kp: KnowledgePoint, set_no: int) -> RewardSummaryOut:
    sp = rewards.get_set_progress(db, user.id, kp.id, set_no)
    live = rewards.count_flowers(db, user.id, kp.id, set_no)
    flowers = max((sp.flowers_earned or 0) if sp else 0, live)
    stars = (sp.stars_earned or 0) if sp else 0
    medals = (sp.medals_granted or 0) if sp else 0
    return RewardSummaryOut(
        knowledge_point_id=str(kp.id),
        set_no=set_no,
        flowers=flowers,
        stars=stars,
        medals=medals,
        exchangeable_stars=rewards.exchangeable_stars_for(flowers, stars),
        can_exchange_medal=rewards.can_exchange_medal_for(stars, medals),
        planet_medals=rewards.planet_medal_count(db, user.id, kp.id),
        set_completed=sp is not None,
    )


@router.get("/summary", response_model=RewardSummaryOut)
def get_summary(
    knowledge_point_id: str | None = None,
    set_no: int | None = None,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    kp, no = _resolve(db, user, knowledge_point_id, set_no)
    return _summary(db, user, kp, no)


@router.get("/exchange-history", response_model=RewardExchangeHistoryOut)
def exchange_history(
    knowledge_point_id: str | None = None,
    limit: int = 50,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    """当前星球的兑换流水（汇总 + 明细，倒序）。"""
    if knowledge_point_id:
        try:
            kp = db.get(KnowledgePoint, uuid.UUID(knowledge_point_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="knowledge_point_id 非法")
        if kp is None:
            raise HTTPException(status_code=404, detail="知识点不存在")
    else:
        kp = resolve_current_kp(db, user)
        if kp is None:
            raise HTTPException(
                status_code=409,
                detail={"detail": "没有当前知识点", "code": "NO_CURRENT_KNOWLEDGE_POINT"},
            )

    def _sum(to_kind: str) -> int:
        return db.execute(
            select(func.coalesce(func.sum(FlowerExchange.amount), 0)).where(
                FlowerExchange.user_id == user.id,
                FlowerExchange.knowledge_point_id == kp.id,
                FlowerExchange.to_kind == to_kind,
            )
        ).scalar_one()

    total_stars = int(_sum("star"))
    total_medals = int(_sum("medal"))
    count = db.execute(
        select(func.count())
        .select_from(FlowerExchange)
        .where(FlowerExchange.user_id == user.id, FlowerExchange.knowledge_point_id == kp.id)
    ).scalar_one()
    last_at = db.execute(
        select(func.max(FlowerExchange.created_at)).where(
            FlowerExchange.user_id == user.id, FlowerExchange.knowledge_point_id == kp.id
        )
    ).scalar_one()
    rows = db.execute(
        select(FlowerExchange)
        .where(FlowerExchange.user_id == user.id, FlowerExchange.knowledge_point_id == kp.id)
        .order_by(FlowerExchange.created_at.desc())
        .limit(max(1, min(limit, 200)))
    ).scalars().all()
    return RewardExchangeHistoryOut(
        knowledge_point_id=str(kp.id),
        total_stars=total_stars,
        total_medals=total_medals,
        flowers_spent=total_stars * 3,
        exchange_count=count,
        last_at=last_at,
        items=[
            RewardExchangeHistoryItem(
                created_at=r.created_at,
                set_no=r.set_no,
                from_kind=r.from_kind,
                to_kind=r.to_kind,
                amount=r.amount,
            )
            for r in rows
        ],
    )


@router.post("/exchange", response_model=RewardExchangeResponse)
def exchange(
    payload: RewardExchangeRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    kp, no = _resolve(db, user, payload.knowledge_point_id, payload.set_no)

    try:
        if payload.from_kind == "flower":
            rewards.exchange_flowers_to_stars(
                db, user.id, kp.id, no, payload.amount,
                idempotency_key=payload.idempotency_key,
            )
        else:
            rewards.exchange_stars_to_medal(
                db, user.id, kp.id, no, payload.amount,
                idempotency_key=payload.idempotency_key,
            )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"detail": str(exc), "code": "EXCHANGE_REJECTED"},
        )

    db.commit()
    return RewardExchangeResponse(ok=True, summary=_summary(db, user, kp, no))
