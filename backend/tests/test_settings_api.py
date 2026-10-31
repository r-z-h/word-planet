"""设置页后端：修改密码 / 清空进度。"""

from tests.conftest import answer_of


def test_change_password_wrong_old(user_client):
    r = user_client.post(
        "/api/change-password",
        json={"old_password": "definitely-wrong", "new_password": "newpass123"},
    )
    assert r.status_code == 401, r.text
    assert r.json()["detail"]["code"] == "WRONG_PASSWORD"


def test_change_password_ok_then_login(user_client):
    r = user_client.post(
        "/api/change-password",
        json={"old_password": "abc123456", "new_password": "brandnew123"},
    )
    assert r.status_code == 200, r.text

    r2 = user_client.post(
        "/api/login",
        json={"account": user_client.account, "password": "brandnew123"},
    )
    assert r2.status_code == 200, r2.text


def test_reset_progress_clears_learning_data(l1_client):
    c = l1_client
    # 先做两题，产生作答/花
    for _ in range(2):
        q = c.get("/api/question/next").json()["question"]
        c.post(
            "/api/answer/submit",
            json={
                "question_id": q["id"],
                "answer": answer_of(q["id"]),
                "idempotency_key": "rst" + q["id"][:24],
            },
        )
    before = c.get("/api/lesson/map").json()
    assert before["today_flowers"] == 2

    r = c.post("/api/reset-progress")
    assert r.status_code == 200, r.text

    after = c.get("/api/lesson/map").json()
    assert after["today_flowers"] == 0
    assert after["today_attempts"] == 0
    assert all(p["completed_sets"] == 0 and p["medals"] == 0 for p in after["planets"])
    # 等级保留
    assert after["level"] == "L1"
    assert after["current_planet_id"] is None
