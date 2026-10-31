"""三层奖励接口测试（走真实 HTTP 层：TestClient）。"""

import uuid

from tests.conftest import answer_of, complete_current_kp


def _submit(c, qid):
    return c.post(
        "/api/answer/submit",
        json={
            "question_id": qid,
            "answer": answer_of(qid),
            "idempotency_key": uuid.uuid4().hex,
        },
    )


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"[:64]


def test_progress_shows_live_flowers_before_set_finished(l1_client):
    c = l1_client
    for _ in range(3):
        q = c.get("/api/question/next").json()["question"]
        assert _submit(c, q["id"]).status_code == 200

    p = c.get("/api/progress").json()
    assert p["set_flowers"] == 3, p
    assert p["exchangeable_stars"] == 1
    assert p["set_stars"] == 0
    assert p["set_medals"] == 0


def test_full_set_then_exchange_to_medal(l1_client):
    c = l1_client
    p = c.get("/api/progress").json()
    kp_id = p["current_knowledge_point"]["id"]
    assert p["set_no"] == 1
    assert p["set_flowers"] == 0

    assert complete_current_kp(c) is True

    s = c.get(
        "/api/reward/summary", params={"knowledge_point_id": kp_id, "set_no": 1}
    ).json()
    assert s["flowers"] == 15, s
    assert s["exchangeable_stars"] == 5
    assert s["set_completed"] is True

    for i in range(5):
        r = c.post(
            "/api/reward/exchange",
            json={
                "knowledge_point_id": kp_id,
                "set_no": 1,
                "from_kind": "flower",
                "amount": 1,
                "idempotency_key": _key(f"flower{i}"),
            },
        )
        assert r.status_code == 200, r.text

    s = c.get(
        "/api/reward/summary", params={"knowledge_point_id": kp_id, "set_no": 1}
    ).json()
    assert s["stars"] == 5 and s["exchangeable_stars"] == 0 and s["can_exchange_medal"] is True

    r = c.post(
        "/api/reward/exchange",
        json={
            "knowledge_point_id": kp_id,
            "set_no": 1,
            "from_kind": "star",
            "amount": 1,
            "idempotency_key": _key("medal"),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["medals"] == 1
    assert body["summary"]["planet_medals"] == 1

    # 再兑一枚：每套最多 1 个 -> 409
    r2 = c.post(
        "/api/reward/exchange",
        json={
            "knowledge_point_id": kp_id,
            "set_no": 1,
            "from_kind": "star",
            "amount": 1,
            "idempotency_key": _key("medal2"),
        },
    )
    assert r2.status_code == 409, r2.text


def test_exchange_idempotent_at_api(l1_client):
    c = l1_client
    p = c.get("/api/progress").json()
    kp_id = p["current_knowledge_point"]["id"]
    complete_current_kp(c)

    payload = {
        "knowledge_point_id": kp_id,
        "set_no": 1,
        "from_kind": "flower",
        "amount": 1,
        "idempotency_key": "same-key-for-idem",
    }
    r1 = c.post("/api/reward/exchange", json=payload)
    assert r1.status_code == 200, r1.text
    stars1 = r1.json()["summary"]["stars"]

    r2 = c.post("/api/reward/exchange", json=payload)
    assert r2.status_code == 200, r2.text
    assert r2.json()["summary"]["stars"] == stars1  # 同 key 不重复扣


def test_exchange_rejected_when_not_enough_flowers(l1_client):
    c = l1_client
    p = c.get("/api/progress").json()
    kp_id = p["current_knowledge_point"]["id"]
    complete_current_kp(c)  # 15 朵花

    for i in range(5):  # 兑满 5 星
        r = c.post(
            "/api/reward/exchange",
            json={
                "knowledge_point_id": kp_id,
                "set_no": 1,
                "from_kind": "flower",
                "amount": 1,
                "idempotency_key": _key(f"f{i}"),
            },
        )
        assert r.status_code == 200, r.text

    r = c.post(
        "/api/reward/exchange",
        json={
            "knowledge_point_id": kp_id,
            "set_no": 1,
            "from_kind": "flower",
            "amount": 1,
            "idempotency_key": _key("extra"),
        },
    )
    assert r.status_code == 409, r.text
