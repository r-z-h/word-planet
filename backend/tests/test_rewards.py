"""三层奖励：记账服务单测 + 接口级测试。"""

import uuid

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Attempt, KnowledgePoint, Question, SetProgress, User
from app.services import rewards
from app.services.attempts import local_today


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _user(db) -> User:
    u = User(account="r_" + uuid.uuid4().hex[:10], password_hash="x", nickname="奖励测试")
    db.add(u)
    db.flush()
    return u


def _kp_with_set(db, level: str, order: int, set_no: int = 1):
    kp = db.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.level == level, KnowledgePoint.sort_order == order
        )
    ).scalar_one()
    qs = list(
        db.execute(
            select(Question)
            .where(Question.knowledge_point_id == kp.id, Question.set_no == set_no)
            .order_by(Question.stem)
        ).scalars()
    )
    return kp, qs


def _attempt(db, user_id, q, correct=True):
    db.add(
        Attempt(
            user_id=user_id,
            question_id=q.id,
            question_type="question",
            idempotency_key=uuid.uuid4().hex,
            is_correct=correct,
        )
    )
    db.flush()


def _finish_set(db, u, kp, set_no=1, correct_count=15):
    """模拟「这一套做完了」：建立 set_progress 行，再回填奖励缓存。"""
    sp = SetProgress(
        user_id=u.id,
        knowledge_point_id=kp.id,
        set_no=set_no,
        correct_count=correct_count,
        total_count=15,
    )
    db.add(sp)
    db.flush()
    rewards.recompute_set_progress(db, u.id, kp.id, set_no)
    return sp


# ---------------------------------------------------------------- 记账

def test_award_flower_is_idempotent(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    assert len(qs) >= 15
    for q in qs[:15]:
        assert rewards.award_flower(db, u.id, q) is True
    # 第 16 次（同一题）幂等
    assert rewards.award_flower(db, u.id, qs[0]) is False


def test_recompute_requires_existing_set_row(db):
    """未完成套时，recompute 不建行（否则会被误判为已完成）。"""
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    for q in qs[:15]:
        rewards.award_flower(db, u.id, q)
    assert rewards.get_set_progress(db, u.id, kp.id, 1) is None

    # 真实流程里「答对」同时会有 attempt 记录
    for q in qs[:15]:
        _attempt(db, u.id, q, correct=True)

    sp = _finish_set(db, u, kp)
    assert sp.flowers_earned == 15
    assert sp.is_complete is True


def test_award_flower_rejects_bad_source(db):
    u = _user(db)
    _, qs = _kp_with_set(db, "L1", 2)
    with pytest.raises(ValueError):
        rewards.award_flower(db, u.id, qs[0], source="bogus")


# ---------------------------------------------------------------- 兑换

def test_full_exchange_chain_15_flowers_to_medal(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    for q in qs[:15]:
        rewards.award_flower(db, u.id, q)
    sp = _finish_set(db, u, kp)

    assert rewards.exchangeable_stars(sp) == 5
    assert rewards.can_exchange_medal(sp) is False

    for _ in range(5):
        sp = rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1)

    assert sp.flowers_earned == 15  # 已获得花不因兑换减少
    assert sp.stars_earned == 5
    assert rewards.exchangeable_stars(sp) == 0
    assert rewards.can_exchange_medal(sp) is True

    sp = rewards.exchange_stars_to_medal(db, u.id, kp.id, 1)
    assert sp.medals_granted == 1
    assert rewards.planet_medal_count(db, u.id, kp.id) == 1

    with pytest.raises(ValueError):
        rewards.exchange_stars_to_medal(db, u.id, kp.id, 1)  # 每套最多 1 个


def test_exchange_is_idempotent_by_key(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    for q in qs[:3]:
        rewards.award_flower(db, u.id, q)
    _finish_set(db, u, kp)

    key = "k" * 12
    rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1, 1, idempotency_key=key)
    sp2 = rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1, 1, idempotency_key=key)
    assert sp2.stars_earned == 1  # 第二次同 key 不重复扣


def test_exchange_over_limit_raises(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    for q in qs[:2]:
        rewards.award_flower(db, u.id, q)
    sp = _finish_set(db, u, kp)
    assert rewards.exchangeable_stars(sp) == 0
    with pytest.raises(ValueError):
        rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1)


def test_partial_exchange_keeps_remainder(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    for q in qs[:5]:
        rewards.award_flower(db, u.id, q)
    sp = _finish_set(db, u, kp)
    assert rewards.exchangeable_stars(sp) == 1

    sp = rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1)
    assert sp.flowers_earned == 5 and sp.stars_earned == 1
    assert rewards.exchangeable_stars(sp) == 0


def test_exchange_without_progress_raises(db):
    u = _user(db)
    kp, _ = _kp_with_set(db, "L1", 2)
    with pytest.raises(ValueError):
        rewards.exchange_flowers_to_stars(db, u.id, kp.id, 99)


# ---------------------------------------------------------------- 纯练星球

def test_pure_planet_complete_without_flowers(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 1)  # 字母表 letter，纯练
    assert kp.counts_for_gate is False
    for q in qs:
        _attempt(db, u.id, q, correct=True)
    sp = _finish_set(db, u, kp)
    assert sp.flowers_earned == 0
    assert sp.is_complete is True


def test_incomplete_when_not_all_correct(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 1)
    for q in qs[:-1]:
        _attempt(db, u.id, q, correct=True)
    sp = _finish_set(db, u, kp, correct_count=len(qs) - 1)
    assert sp.is_complete is False


# ---------------------------------------------------------------- 今日星

def test_today_stars_counts_only_star_exchanges(db):
    u = _user(db)
    kp, qs = _kp_with_set(db, "L1", 2)
    for q in qs[:6]:
        rewards.award_flower(db, u.id, q)
    _finish_set(db, u, kp)
    rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1)
    rewards.exchange_flowers_to_stars(db, u.id, kp.id, 1)
    db.flush()
    assert rewards.stars_exchanged_on(db, u.id, local_today(db)) == 2
