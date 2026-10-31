"""星球地图接口测试。"""


def test_map_returns_seven_planets(l1_client):
    resp = l1_client.get("/api/lesson/map")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["planets"]) == 7
    names = {p["name"] for p in data["planets"]}
    assert names == {"字母表", "基础问候词", "常用单词", "简单拼写", "单词跟读", "听力理解", "拼写进阶"}

    by_name = {p["name"]: p for p in data["planets"]}
    # L1 可用、L2/L3 锁定（l1_client 的 max_level=L1）
    assert by_name["字母表"]["locked"] is False
    assert by_name["基础问候词"]["locked"] is False
    assert by_name["常用单词"]["locked"] is True
    assert by_name["拼写进阶"]["locked"] is True

    # 纯练标记
    assert by_name["字母表"]["pure"] is True
    assert by_name["听力理解"]["pure"] is True
    assert by_name["基础问候词"]["pure"] is False

    # 当前星球
    assert by_name["基础问候词"]["is_current"] is True
    assert data["current_planet_id"] == by_name["基础问候词"]["id"]

    # 徽记上限 = 套数
    assert by_name["基础问候词"]["max_medals"] == by_name["基础问候词"]["total_sets"] > 0
    assert by_name["基础问候词"]["medals"] == 0


def test_map_today_flowers_after_answers(l1_client):
    from tests.conftest import answer_of

    c = l1_client
    for _ in range(2):
        q = c.get("/api/question/next").json()["question"]
        r = c.post(
            "/api/answer/submit",
            json={"question_id": q["id"], "answer": answer_of(q["id"]), "idempotency_key": "map" + q["id"][:20]},
        )
        assert r.status_code == 200, r.text
    data = c.get("/api/lesson/map").json()
    assert data["today_flowers"] == 2
