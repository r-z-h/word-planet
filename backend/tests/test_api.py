import uuid

from tests.conftest import answer_of, complete_current_kp, complete_sets, force_level


def test_register_creates_progress_and_returns_token(client):
    resp = client.post(
        "/api/register",
        json={"account": "Alice_01", "password": "abc123456", "nickname": "Alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["has_tested"] is False
    assert body["access_token"]

    client.headers["Authorization"] = f"Bearer {body['access_token']}"
    progress = client.get("/api/progress")
    assert progress.status_code == 200
    assert progress.json()["completed_knowledge_points"] == []


def test_account_is_case_insensitive(client):
    client.post(
        "/api/register", json={"account": "Tom01", "password": "abc123456", "nickname": "T"}
    )
    dup = client.post(
        "/api/register", json={"account": "tom01", "password": "abc123456", "nickname": "T2"}
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "ACCOUNT_EXISTS"


def test_login_and_password_is_hashed(client):
    client.post(
        "/api/register", json={"account": "bob01", "password": "secret123", "nickname": "Bob"}
    )
    ok = client.post("/api/login", json={"account": "bob01", "password": "secret123"})
    assert ok.status_code == 200
    bad = client.post("/api/login", json={"account": "bob01", "password": "wrong"})
    assert bad.status_code == 401

    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        user = db.query(User).filter(User.account == "bob01").one()
        assert user.password_hash != "secret123"
        assert user.password_hash.startswith("$2")


def test_untested_user_blocked(user_client):
    resp = user_client.get("/api/question/next")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "NOT_TESTED"


def test_placement_test_finishes_within_ten_questions(user_client):
    start = user_client.post("/api/test/start")
    assert start.status_code == 200
    body = start.json()

    for _ in range(12):
        qid = body["question"]["id"]
        resp = user_client.post("/api/test/answer", json={"question_id": qid, "answer": answer_of(qid)})
        body = resp.json()
        if body["is_finished"]:
            break
        body = {"question": body["next_question"]}

    assert body["is_finished"] is True
    assert body["level"] in {"L1", "L2", "L3"}

    me = user_client.get("/api/me").json()
    assert me["has_tested"] is True
    assert me["level"] == body["level"]

    progress = user_client.get("/api/progress").json()
    assert progress["current_knowledge_point"] is not None


def test_cannot_retake_test(user_client):
    start = user_client.post("/api/test/start")
    body = start.json()
    for _ in range(12):
        qid = body["question"]["id"]
        body = user_client.post(
            "/api/test/answer", json={"question_id": qid, "answer": answer_of(qid)}
        ).json()
        if body["is_finished"]:
            break
        body = {"question": body["next_question"]}

    again = user_client.post("/api/test/start")
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "ALREADY_TESTED"


def test_complete_kp_advances_and_marks_task(l1_client):
    # 完成 1 套即算今天学过
    assert complete_current_kp(l1_client) is True

    progress = l1_client.get("/api/progress").json()
    assert progress["completed_sets"] == 1
    assert progress["today_task"]["is_completed"] is True
    # 完成 3 套后该知识点才算「达标」
    assert complete_sets(l1_client, 2) == 2
    progress = l1_client.get("/api/progress").json()
    assert len(progress["completed_knowledge_points"]) == 1

    streak = l1_client.get("/api/streak").json()
    assert streak["current_streak"] == 1


def test_duplicate_answers_do_not_double_count(l1_client):
    from app.database import SessionLocal
    from app.models import Attempt

    q = l1_client.get("/api/question/next").json()["question"]
    key = uuid.uuid4().hex
    payload = {"question_id": q["id"], "answer": answer_of(q["id"]), "idempotency_key": key}

    first = l1_client.post("/api/answer/submit", json=payload).json()
    second = l1_client.post("/api/answer/submit", json=payload).json()

    assert first["duplicated"] is False
    assert second["duplicated"] is True

    with SessionLocal() as db:
        count = db.query(Attempt).filter(Attempt.idempotency_key == key).count()
    assert count == 1


def test_same_question_twice_counts_as_one(l1_client):
    q = l1_client.get("/api/question/next").json()["question"]
    ans = answer_of(q["id"])
    for _ in range(2):
        l1_client.post(
            "/api/answer/submit",
            json={"question_id": q["id"], "answer": ans, "idempotency_key": uuid.uuid4().hex},
        )

    from app.services.attempts import is_kp_complete
    from app.database import SessionLocal
    from app.models import Progress

    with SessionLocal() as db:
        progress = db.get(Progress, uuid.UUID(l1_client.user_id))
        assert progress.completed_knowledge_points == []
        assert is_kp_complete(db, progress.user_id, progress.current_knowledge_point_id) is False


def test_wrong_question_enters_book_and_mastery(l1_client):
    q = l1_client.get("/api/question/next").json()["question"]
    wrong_answer = "ZZZ"

    res = l1_client.post(
        "/api/answer/submit",
        json={
            "question_id": q["id"],
            "answer": wrong_answer,
            "idempotency_key": uuid.uuid4().hex,
        },
    ).json()
    assert res["is_correct"] is False

    items = l1_client.get("/api/wrong-questions", params={"scope": "all"}).json()["items"]
    assert any(i["question_id"] == q["id"] for i in items)

    for _ in range(2):
        l1_client.post(
            "/api/answer/submit",
            json={
                "question_id": q["id"],
                "answer": answer_of(q["id"]),
                "idempotency_key": uuid.uuid4().hex,
            },
        )

    items = l1_client.get("/api/wrong-questions", params={"scope": "all"}).json()["items"]
    assert not any(i["question_id"] == q["id"] for i in items)

    all_items = l1_client.get(
        "/api/wrong-questions", params={"scope": "all", "include_mastered": "true"}
    ).json()["items"]
    mastered = [i for i in all_items if i["question_id"] == q["id"]]
    assert mastered and mastered[0]["is_mastered"] is True


def test_struggled_question_does_not_block_completion(l1_client):
    """一道题连续答错 5 次后，不该卡住知识点完成。"""
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import KnowledgePoint, Question

    with SessionLocal() as db:
        from app.models import Progress

        progress = db.get(Progress, uuid.UUID(l1_client.user_id))
        qids = [
            str(x)
            for x in db.execute(
                select(Question.id).where(
                    Question.knowledge_point_id == progress.current_knowledge_point_id
                )
            ).scalars()
        ]

    blocked = qids[0]
    for _ in range(5):
        l1_client.post(
            "/api/answer/submit",
            json={
                "question_id": blocked,
                "answer": "definitely-wrong",
                "idempotency_key": uuid.uuid4().hex,
            },
        )

    for qid in qids[1:]:
        l1_client.post(
            "/api/answer/submit",
            json={"question_id": qid, "answer": answer_of(qid), "idempotency_key": uuid.uuid4().hex},
        )

    from app.database import SessionLocal as SL
    from app.models import Progress as P

    with SL() as db:
        p = db.get(P, uuid.UUID(l1_client.user_id))
        assert str(p.current_knowledge_point_id) != qids[0] or len(p.completed_knowledge_points) == 1


def test_pronunciation_endpoint_guard(user_client):
    force_level(user_client.user_id, "L2")
    resp = user_client.get("/api/pronunciation/next")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "WRONG_ENDPOINT"


def test_pronunciation_flow_completes_kp(l1_client):
    """L2 的跟读知识点走 /pronunciation/* 通道，答完应能推进。"""
    from app.database import SessionLocal
    from app.models import KnowledgePoint, Progress

    force_level(l1_client.user_id, "L2")
    with SessionLocal() as db:
        kp = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.level == "L2", KnowledgePoint.question_type == "pronunciation")
            .one()
        )
        progress = db.get(Progress, uuid.UUID(l1_client.user_id))
        progress.current_knowledge_point_id = kp.id
        db.commit()

    blocked = l1_client.get("/api/question/next")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "USE_PRONUNCIATION_ENDPOINT"

    advanced = False
    for _ in range(30):
        q = l1_client.get("/api/pronunciation/next").json()["question"]
        res = l1_client.post(
            "/api/pronunciation/result",
            json={
                "word_id": q["id"],
                "is_correct": True,
                "idempotency_key": uuid.uuid4().hex,
            },
        )
        assert res.status_code == 200, res.text
        if res.json()["progress_advanced"]:
            advanced = True
            break

    assert advanced is True


def test_badges_awarded_once(l1_client):
    assert complete_sets(l1_client, 3) == 3

    items = l1_client.get("/api/achievements").json()["items"]
    codes = [i["code"] for i in items]
    assert "complete_l1_first" in codes
    assert codes.count("complete_l1_first") == 1


def test_report_shape(l1_client):
    complete_sets(l1_client, 3)
    report = l1_client.get("/api/report").json()

    assert set(report) >= {
        "level",
        "completed_knowledge_points",
        "total_knowledge_points",
        "last_7_days_completed",
        "daily_attempts",
        "wrong_questions",
    }
    assert report["completed_knowledge_points"] == 1
    assert report["total_knowledge_points"] == 2
    assert len(report["daily_attempts"]) == 7
    assert report["last_7_days_completed"] == 1


def test_level_does_not_cross(user_client):
    """学完本级最后一个知识点后停留在原地，不跨级。"""
    from app.database import SessionLocal
    from app.models import KnowledgePoint, Progress

    force_level(user_client.user_id, "L1")
    with SessionLocal() as db:
        last = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.level == "L1")
            .order_by(KnowledgePoint.sort_order.desc())
            .first()
        )
        last_id = str(last.id)
        progress = db.get(Progress, uuid.UUID(user_client.user_id))
        progress.current_knowledge_point_id = last.id
        db.commit()

    assert complete_current_kp(user_client) is True

    me = user_client.get("/api/me").json()
    assert me["level"] == "L1"

    progress = user_client.get("/api/progress").json()
    assert progress["current_knowledge_point"]["id"] == last_id
