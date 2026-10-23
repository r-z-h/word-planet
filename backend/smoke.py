"""端到端冒烟：真实 HTTP 链路，不用 mock。"""

import uuid

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Attempt, Question

BASE = "http://127.0.0.1:8000"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def answer_of(question_id: str) -> str:
    with SessionLocal() as db:
        q = db.get(Question, uuid.UUID(question_id))
        return str(q.answer)


def main() -> None:
    account = f"smoke_{uuid.uuid4().hex[:8]}"
    client = httpx.Client(base_url=BASE, timeout=20)

    r = client.post(
        "/api/register",
        json={"account": account, "password": "abc123456", "nickname": "冒烟"},
    )
    check("注册返回 201 且带 token", r.status_code == 201 and "access_token" in r.json(), str(r.status_code))
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    r = client.get("/api/progress")
    check("注册后 /progress 返回 200（progress 行已建）", r.status_code == 200, str(r.status_code))

    r = client.get("/api/question/next")
    check("未测试调 /question/next 返回 409 NOT_TESTED", r.status_code == 409 and r.json()["detail"]["code"] == "NOT_TESTED", str(r.status_code))

    # ---- 水平测试
    r = client.post("/api/test/start")
    check("测试开始", r.status_code == 200, str(r.status_code))
    body = r.json()

    finished = False
    for _ in range(12):
        qid = body["question"]["id"]
        r = client.post("/api/test/answer", json={"question_id": qid, "answer": answer_of(qid)})
        body = r.json()
        if body["is_finished"]:
            finished = True
            break
        # 下一次的题目在 next_question 里
        body = {"question": body["next_question"]}

    check("测试在 10 题内结束并返回等级", finished and body.get("level") in {"L1", "L2", "L3"}, str(body.get("level")))

    r = client.get("/api/me")
    check("测试后 has_tested=true 且 level 非空", r.json()["has_tested"] and r.json()["level"], str(r.json()))

    r = client.get("/api/progress")
    check("测试后 current_knowledge_point 非空", r.json()["current_knowledge_point"] is not None)

    # ---- 答题直到知识点完成
    advanced = False
    for _ in range(40):
        r = client.get("/api/question/next")
        if r.status_code != 200:
            check("出题成功", False, r.text[:120])
            return
        q = r.json()["question"]
        r = client.post(
            "/api/answer/submit",
            json={
                "question_id": q["id"],
                "answer": answer_of(q["id"]),
                "idempotency_key": uuid.uuid4().hex,
            },
        )
        if r.status_code != 200:
            check("提交答题成功", False, r.text[:200])
            return
        if r.json()["progress_advanced"]:
            advanced = True
            break

    check("答完知识点后 progress_advanced=true", advanced)

    r = client.get("/api/progress")
    p = r.json()
    check("已完成知识点被记录", len(p["completed_knowledge_points"]) == 1, str(p["completed_knowledge_points"]))
    check("当天任务标记完成", p["today_task"]["is_completed"] is True, str(p["today_task"]))

    r = client.get("/api/streak")
    check("连续学习已 +1", r.json()["current_streak"] == 1, str(r.json()))

    r = client.get("/api/achievements")
    codes = [i["code"] for i in r.json()["items"]]
    check("L3 用户不应拿到 L1 徽章", "complete_l1_first" not in codes, str(codes))

    # ---- 幂等
    r = client.get("/api/question/next")
    q = r.json()["question"]
    key = uuid.uuid4().hex
    payload = {"question_id": q["id"], "answer": answer_of(q["id"]), "idempotency_key": key}
    first = client.post("/api/answer/submit", json=payload).json()
    second = client.post("/api/answer/submit", json=payload).json()
    check("重复幂等键返回 duplicated=true", second["duplicated"] is True)
    check("两次结果一致", first["is_correct"] == second["is_correct"])

    with SessionLocal() as db:
        cnt = len(db.execute(select(Attempt).where(Attempt.idempotency_key == key)).scalars().all())
    check("幂等键只落一条 attempts", cnt == 1, f"count={cnt}")

    # ---- 错题与报告
    r = client.get("/api/wrong-questions")
    check("错题本可访问", r.status_code == 200, str(r.status_code))

    r = client.get("/api/report")
    rep = r.json()
    check("报告字段齐全", set(rep) >= {"level", "completed_knowledge_points", "total_knowledge_points", "last_7_days_completed", "daily_attempts", "wrong_questions"})
    check("报告：已完成知识点数 = 1", rep["completed_knowledge_points"] == 1, str(rep["completed_knowledge_points"]))
    check("报告：同等级知识点总数 = 2/3", rep["total_knowledge_points"] in (2, 3), str(rep["total_knowledge_points"]))
    check("报告：近 7 天完成天数 = 1", rep["last_7_days_completed"] == 1, str(rep["last_7_days_completed"]))
    check("报告：daily_attempts 为 7 天", len(rep["daily_attempts"]) == 7)

    # ---- 跟读分流
    r = client.get("/api/pronunciation/next")
    check("非跟读知识点调 /pronunciation/next 返回 409 WRONG_ENDPOINT", r.status_code == 409 and r.json()["detail"]["code"] == "WRONG_ENDPOINT", str(r.status_code))

    # ---- L1 徽章场景（直接把用户放到 L1，验证 complete_kp 条件）
    from app.models import KnowledgePoint, Progress, User

    account2 = f"smoke_l1_{uuid.uuid4().hex[:6]}"
    c2 = httpx.Client(base_url=BASE, timeout=20)
    r = c2.post(
        "/api/register",
        json={"account": account2, "password": "abc123456", "nickname": "L1娃"},
    )
    c2.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.level == "L1")
            .order_by(KnowledgePoint.sort_order)
        ).scalars().first()
        u = db.execute(select(User).where(User.account == account2)).scalar_one()
        u.level = "L1"
        u.has_tested = True
        p = db.get(Progress, u.id)
        p.current_knowledge_point_id = kp.id
        db.commit()

    done = False
    for _ in range(30):
        q = c2.get("/api/question/next").json()["question"]
        rr = c2.post(
            "/api/answer/submit",
            json={
                "question_id": q["id"],
                "answer": answer_of(q["id"]),
                "idempotency_key": uuid.uuid4().hex,
            },
        )
        if rr.json()["progress_advanced"]:
            done = True
            break

    check("L1 场景：知识点完成并推进", done)
    codes = [i["code"] for i in c2.get("/api/achievements").json()["items"]]
    check("L1 用户拿到 complete_l1_first 徽章", "complete_l1_first" in codes, str(codes))

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n共 {len(RESULTS)} 项，通过 {len(RESULTS) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败项：" + "，".join(failed))
        raise SystemExit(1)

if __name__ == "__main__":
    main()
