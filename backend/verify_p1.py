"""验证 P1：错题练习、解析、进度条字段。"""

import uuid

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint, Progress, Question, User

BASE = "http://127.0.0.1:8000"
R = []


def check(name, ok, detail=""):
    R.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def answer_of(qid):
    with SessionLocal() as db:
        return str(db.get(Question, uuid.UUID(qid)).answer)


def main():
    c = httpx.Client(base_url=BASE, timeout=20)
    acc = f"p1_{uuid.uuid4().hex[:8]}"
    r = c.post("/api/register", json={"account": acc, "password": "abc123456", "nickname": "P1"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    user_id = r.json()["user_id"]

    # 直接放到 L1，跳过测试
    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint).where(KnowledgePoint.level == "L1").order_by(KnowledgePoint.sort_order)
        ).scalars().first()
        u = db.get(User, uuid.UUID(user_id))
        u.level = "L1"
        u.has_tested = True
        p = db.get(Progress, u.id)
        p.current_knowledge_point_id = kp.id
        db.commit()

    # 进度字段
    prog = c.get("/api/progress").json()
    check("progress 返回 kp_total / kp_done", prog.get("kp_total") == 15 and prog.get("kp_done") == 0,
          f"{prog.get('kp_total')}/{prog.get('kp_done')}")

    # 答错一题 -> 进错题本
    q = c.get("/api/question/next").json()["question"]
    c.post("/api/answer/submit", json={"question_id": q["id"], "answer": "###", "idempotency_key": uuid.uuid4().hex})

    book = c.get("/api/wrong-questions", params={"scope": "all"}).json()["items"]
    check("错题进本", any(i["question_id"] == q["id"] for i in book))
    check("错题带解析", all(i.get("explanation") for i in book), str(len(book)))

    # 练习出题
    pn = c.get("/api/practice/next")
    check("练习出题 200", pn.status_code == 200, str(pn.status_code))
    pj = pn.json()["question"]
    check("练习题带解析", bool(pj.get("explanation")))
    check("练习剩余数正确", pn.json()["remaining"] == 1, str(pn.json()["remaining"]))

    # 练习答错
    r1 = c.post("/api/practice/result", json={
        "question_id": pj["id"], "answer": "###", "idempotency_key": uuid.uuid4().hex
    }).json()
    check("练习答错不计掌握", r1["is_correct"] is False and r1["mastered"] is False)

    # 连对两次 -> 掌握
    for _ in range(2):
        r2 = c.post("/api/practice/result", json={
            "question_id": pj["id"], "answer": answer_of(pj["id"]), "idempotency_key": uuid.uuid4().hex
        }).json()
    check("连对 2 次判定掌握", r2["mastered"] is True, f"consecutive={r2['consecutive_correct']}")

    # 掌握后移出默认列表
    default_book = c.get("/api/wrong-questions", params={"scope": "all"}).json()["items"]
    check("掌握后移出默认列表", not any(i["question_id"] == pj["id"] for i in default_book))

    full = c.get("/api/wrong-questions", params={"scope": "all", "include_mastered": "true"}).json()["items"]
    check("include_mastered 仍能查到", any(i["question_id"] == pj["id"] for i in full))

    # 汇总
    s = c.get("/api/practice/summary").json()
    check("summary 统计正确", s["pending"] == 0 and s["mastered"] == 1, f"pending={s['pending']} mastered={s['mastered']}")

    # 练习不推进知识点
    prog2 = c.get("/api/progress").json()
    check("练习不影响知识点进度", prog2["kp_done"] == 1, f"kp_done={prog2['kp_done']}")

    failed = [n for n, ok in R if not ok]
    print(f"\n共 {len(R)} 项，通过 {len(R)-len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败：" + "，".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
