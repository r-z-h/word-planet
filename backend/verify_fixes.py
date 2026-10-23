"""针对用户反馈的 5 个问题做定向验证（真实 HTTP）。"""

import uuid

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Question

BASE = "http://127.0.0.1:8000"
R: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    R.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def answer_of(qid: str) -> str:
    with SessionLocal() as db:
        return str(db.get(Question, uuid.UUID(qid)).answer)


def main():
    c = httpx.Client(base_url=BASE, timeout=20)
    acc = f"fix_{uuid.uuid4().hex[:8]}"
    r = c.post("/api/register", json={"account": acc, "password": "abc123456", "nickname": "验证"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    # 水平测试
    body = c.post("/api/test/start").json()
    test_ids = []
    while True:
        qid = body["question"]["id"]
        test_ids.append(qid)
        body = c.post("/api/test/answer", json={"question_id": qid, "answer": answer_of(qid)}).json()
        if body["is_finished"]:
            break
        body = {"question": body["next_question"]}

    print("测试出过的题数：", len(test_ids))

    # 问题1：学习阶段不再撞测试题
    first = c.get("/api/question/next").json()["question"]
    check("问题1 首题不是测试出过的题", first["id"] not in test_ids, first["id"])

    # 重复请求应返回同一题（问题5 的前半：恢复未答完的题）
    again = c.get("/api/question/next").json()["question"]
    check("问题5 再次进入返回同一道未答题", again["id"] == first["id"], f"{again['id']} vs {first['id']}")

    before = c.get("/api/progress").json()["today_task"]["target_count"]

    # 问题2 + 4：答错 -> 入错题本，且下一题不是同一道
    wrong = c.post(
        "/api/answer/submit",
        json={"question_id": first["id"], "answer": "###", "idempotency_key": uuid.uuid4().hex},
    ).json()
    check("答错返回 is_correct=false", wrong["is_correct"] is False)

    book = c.get("/api/wrong-questions", params={"scope": "all"}).json()["items"]
    check(
        "问题2 答错立刻进错题本",
        any(i["question_id"] == first["id"] for i in book),
        f"共 {len(book)} 条",
    )

    nxt = c.get("/api/question/next").json()["question"]
    check("问题4 答错后不重复同一题", nxt["id"] != first["id"], f"{nxt['id']} vs {first['id']}")

    # 问题3：答对后“还剩 N 题”实时递减
    c.post(
        "/api/answer/submit",
        json={"question_id": nxt["id"], "answer": answer_of(nxt["id"]), "idempotency_key": uuid.uuid4().hex},
    )
    after = c.get("/api/progress").json()["today_task"]["target_count"]
    check("问题3 答对后剩余题数递减", after == before - 1, f"{before} -> {after}")

    failed = [n for n, ok, _ in R if not ok]
    print(f"\n共 {len(R)} 项，通过 {len(R) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败：" + "，".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
