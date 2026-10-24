"""验证按套推进、门槛、能力测试、等级回访。"""

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


def make_user(level="L1", kp_index=1):
    c = httpx.Client(base_url=BASE, timeout=20)
    acc = f"set_{uuid.uuid4().hex[:8]}"
    r = c.post("/api/register", json={"account": acc, "password": "abc123456", "nickname": "S"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    uid = r.json()["user_id"]
    with SessionLocal() as db:
        kps = db.execute(
            select(KnowledgePoint).where(KnowledgePoint.level == level).order_by(KnowledgePoint.sort_order)
        ).scalars().all()
        u = db.get(User, uuid.UUID(uid))
        u.level = level
        u.max_level = level
        u.has_tested = True
        p = db.get(Progress, u.id)
        p.current_knowledge_point_id = kps[kp_index].id
        db.commit()
        return c, uid, str(kps[kp_index].id)


def finish_set(c, correct=True):
    """把当前这一套答完。"""
    for _ in range(20):
        resp = c.get("/api/question/next")
        if resp.status_code != 200:
            return None
        data = resp.json()
        q = data["question"]
        ans = answer_of(q["id"]) if correct else "###"
        res = c.post(
            "/api/answer/submit",
            json={"question_id": q["id"], "answer": ans, "idempotency_key": uuid.uuid4().hex},
        )
        if res.status_code != 200:
            return None
        if res.json()["progress_advanced"]:
            return data["set_no"]
    return None


def main():
    c, uid, kp_id = make_user()

    ov = c.get("/api/lesson/overview").json()
    check("overview 返回 2 个 L1 知识点", len(ov["knowledge_points"]) == 2, str(len(ov["knowledge_points"])))
    check("初始未达门槛", ov["gate_ready"] is False)
    check("字母表不计入门槛", any(k["counts_for_gate"] is False for k in ov["knowledge_points"]))

    nxt = c.get("/api/question/next").json()
    check("第 1 套、共 15 题", nxt["set_no"] == 1 and nxt["set_total"] == 15, f"{nxt['set_no']}/{nxt['set_total']}")

    s1 = finish_set(c)
    check("答完第 1 套触发完成", s1 == 1, str(s1))

    prog = c.get("/api/progress").json()
    check("进度：已完成 1 套、当前第 2 套", prog["completed_sets"] == 1 and prog["set_no"] == 2,
          f"{prog['completed_sets']}/{prog['set_no']}")

    s2 = finish_set(c)
    s3 = finish_set(c)
    check("第 2、3 套依次完成", s2 == 2 and s3 == 3, f"{s2},{s3}")

    ov2 = c.get("/api/lesson/overview").json()
    check("三套后达门槛", ov2["gate_ready"] is True)
    check("能力测试可点", ov2["can_test"] is True)

    st = c.get("/api/level-test/status").json()
    check("status 可测", st["can_test"] is True)

    # 重复做已完成的套：不应增加套数
    c.post("/api/lesson/select", json={"knowledge_point_id": kp_id})
    before = c.get("/api/progress").json()["completed_sets"]
    check("重复进入不改变套数", before == 3, str(before))

    # 能力测试：10 题答对 8 题
    start = c.post("/api/level-test/start")
    check("测试开始", start.status_code == 200, str(start.status_code))
    body = start.json()
    score = 0
    finished = None
    for i in range(10):
        qid = body["question"]["id"]
        correct = i < 8
        res = c.post("/api/level-test/answer",
                     json={"question_id": qid, "answer": answer_of(qid) if correct else "###"})
        if res.status_code != 200:
            check("测试答题", False, res.text[:80]); return
        data = res.json()
        if data["is_finished"]:
            finished = data
            break
        body = c.get("/api/level-test/next").json()

    check("测试 10 题结束，得分 8", finished and finished["score"] == 8, str(finished and finished["score"]))
    check("8 分通过", finished and finished["passed"] is True)

    # 选择升级
    ch = c.post("/api/level-test/choose", json={"go_next": True}).json()
    check("选择升级到 L2", ch["level"] == "L2", ch["level"])

    # 回访 L1
    back = c.post("/api/lesson/switch-level", json={"level": "L1"}).json()
    check("可回到 L1 继续学", back["level"] == "L1", back["level"])
    check("max_level 保持 L2", back["max_level"] == "L2", back["max_level"])

    # 未解锁等级不可进
    locked = c.post("/api/lesson/switch-level", json={"level": "L3"})
    check("L3 未解锁被拒", locked.status_code == 409, str(locked.status_code))

    failed = [n for n, ok in R if not ok]
    print(f"\n共 {len(R)} 项，通过 {len(R) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败：" + "，".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
