"""错题本补花 & 防抢记（同一题 10 分钟内重复答对不累计连对）。"""

import uuid

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import QuestionFlower, WrongQuestion
from tests.conftest import answer_of


def _put_wrong(client):
    q = client.get("/api/question/next").json()["question"]
    r = client.post(
        "/api/answer/submit",
        json={"question_id": q["id"], "answer": "ZZZ", "idempotency_key": uuid.uuid4().hex},
    )
    assert r.json()["is_correct"] is False
    return q["id"]


def _practice(client, qid):
    return client.post(
        "/api/practice/result",
        json={"question_id": qid, "answer": answer_of(qid), "idempotency_key": uuid.uuid4().hex},
    )


def _wrong_record(user_id, qid):
    with SessionLocal() as db:
        return db.execute(
            select(WrongQuestion).where(
                WrongQuestion.user_id == uuid.UUID(user_id),
                WrongQuestion.question_id == uuid.UUID(qid),
            )
        ).scalar_one_or_none()


def _flower_count(user_id, qid):
    with SessionLocal() as db:
        return db.execute(
            select(func.count())
            .select_from(QuestionFlower)
            .where(
                QuestionFlower.user_id == uuid.UUID(user_id),
                QuestionFlower.question_id == uuid.UUID(qid),
            )
        ).scalar_one()


def test_practice_awards_flower_after_mastery(l1_client, monkeypatch):
    # 关掉冷却，模拟"分次答对 3 次"
    monkeypatch.setattr("app.routers.practice.PRACTICE_COOLDOWN_MINUTES", 0)
    uid = l1_client.user_id
    qid = _put_wrong(l1_client)

    body = None
    for _ in range(3):
        r = _practice(l1_client, qid)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["counted"] is True, "冷却关闭时每次答对都应累计"

    assert body["mastered"] is True
    assert body["flower_gained"] is True, "第 3 次连对应补 1 朵花"
    assert _flower_count(uid, qid) == 1, "连续答对 3 次后应补发 1 朵花"
    rec = _wrong_record(uid, qid)
    assert rec.consecutive_correct >= 3


def test_practice_one_fetches_specific_question(l1_client):
    qid = _put_wrong(l1_client)
    r = l1_client.get("/api/practice/one", params={"question_id": qid})
    assert r.status_code == 200, r.text
    assert r.json()["question"]["id"] == qid

    # 不在错题本的题应被拒
    other = l1_client.get("/api/question/next").json()["question"]
    r2 = l1_client.get("/api/practice/one", params={"question_id": other["id"]})
    assert r2.status_code in (409, 404), r2.text


def test_practice_cooldown_blocks_cram(l1_client):
    # 默认 10 分钟冷却：10 分钟内重复答对只算 1 次，不补花，并返回提示字段
    uid = l1_client.user_id
    qid = _put_wrong(l1_client)

    r1 = _practice(l1_client, qid)
    assert r1.status_code == 200, r1.text
    assert r1.json()["counted"] is True

    r2 = _practice(l1_client, qid)
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["counted"] is False, "10 分钟内重复答对不应累计连对"
    assert b2["cooldown_remaining"] > 0, "应返回距下次可计入的剩余秒数，供前端提示"

    assert _flower_count(uid, qid) == 0
    rec = _wrong_record(uid, qid)
    assert rec.consecutive_correct == 1
