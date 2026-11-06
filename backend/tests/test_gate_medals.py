"""升级门槛：6 星球按各自数量；L1→L2 = 字母表完成 + 基础问候词 5 枚；字母表不发花不发徽记。"""

import uuid

from tests.conftest import answer_of, complete_current_kp, complete_sets


def _exchange_medal(client, kp_id, set_no):
    """把某套的花兑成 1 枚星球徽记（15 花 → 5 星 → 1 徽记）。"""
    for _ in range(5):
        r = client.post(
            "/api/reward/exchange",
            json={
                "knowledge_point_id": kp_id,
                "set_no": set_no,
                "from_kind": "flower",
                "amount": 1,
                "idempotency_key": uuid.uuid4().hex,
            },
        )
        assert r.status_code == 200, r.text
    r = client.post(
        "/api/reward/exchange",
        json={
            "knowledge_point_id": kp_id,
            "set_no": set_no,
            "from_kind": "star",
            "amount": 1,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert r.status_code == 200, r.text


def test_l1_gate_letter_complete_plus_5_medals(l1_client):
    c = l1_client
    ov = c.get("/api/lesson/overview").json()
    base = next(k for k in ov["knowledge_points"] if k["name"] == "基础问候词")
    letter = next(k for k in ov["knowledge_points"] if k["name"] == "字母表")
    assert base["gate_mode"] == "medals" and base["gate_required"] == 5
    assert letter["gate_mode"] == "completion"
    assert ov["gate_ready"] is False

    # 完成 5 套基础问候词并各兑 1 枚徽记；但字母表还没完成 -> 仍不达标
    assert complete_sets(c, count=5) == 5
    for s in range(1, 6):
        _exchange_medal(c, base["id"], s)

    ov2 = c.get("/api/lesson/overview").json()
    b2 = next(k for k in ov2["knowledge_points"] if k["name"] == "基础问候词")
    assert b2["medals"] == 5
    assert ov2["gate_ready"] is False, "字母表未完成，不应达标"

    # 完成字母表（15 题全对）
    lc = c.post("/api/lesson/select", json={"knowledge_point_id": letter["id"]})
    assert lc.status_code == 200, lc.text
    assert complete_current_kp(c) is True

    ov3 = c.get("/api/lesson/overview").json()
    le3 = next(k for k in ov3["knowledge_points"] if k["name"] == "字母表")
    assert le3["completed"] is True
    assert ov3["gate_ready"] is True
    assert ov3["can_test"] is True


def test_letter_produces_no_flowers(l1_client):
    c = l1_client
    ov = c.get("/api/lesson/overview").json()
    letter = next(k for k in ov["knowledge_points"] if k["name"] == "字母表")
    c.post("/api/lesson/select", json={"knowledge_point_id": letter["id"]})

    q = c.get("/api/question/next").json()["question"]
    r = c.post(
        "/api/answer/submit",
        json={"question_id": q["id"], "answer": answer_of(q["id"]), "idempotency_key": uuid.uuid4().hex},
    )
    assert r.status_code == 200, r.text

    ps = c.get("/api/lesson/planet-sets", params={"knowledge_point_id": letter["id"]}).json()
    s1 = next(x for x in ps["sets"] if x["set_no"] == 1)
    assert s1["flowers"] == 0, "字母表答对不发花"
