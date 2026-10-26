"""验证词典页接口：等级范围、未学优先、分页、搜索、状态标签、L3 英文释义。"""

import uuid

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint, Progress, Question, User, Word

BASE = "http://127.0.0.1:8000"
R = []


def check(name, ok, detail=""):
    R.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def make_user(level):
    c = httpx.Client(base_url=BASE, timeout=20)
    acc = f"dict_{uuid.uuid4().hex[:8]}"
    r = c.post("/api/register", json={"account": acc, "password": "abc123456", "nickname": "D"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    uid = r.json()["user_id"]
    with SessionLocal() as db:
        kps = (
            db.execute(
                select(KnowledgePoint)
                .where(KnowledgePoint.level == level)
                .order_by(KnowledgePoint.sort_order)
            )
            .scalars()
            .all()
        )
        user = db.get(User, uuid.UUID(uid))
        user.level = level
        user.max_level = level
        user.has_tested = True
        progress = db.get(Progress, user.id)
        progress.current_knowledge_point_id = kps[0].id
        db.commit()
    return c, uid


def target_word(question):
    if question.question_type in ("spelling", "pronunciation"):
        return str(question.answer).strip().lower()
    if isinstance(question.options, dict):
        return str(question.options.get(str(question.answer).upper(), "")).strip().lower()
    return ""


def questions_for(word, level):
    with SessionLocal() as db:
        rows = db.execute(
            select(Question)
            .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
            .where(KnowledgePoint.level == level)
        ).scalars()
        return [q for q in rows if target_word(q) == word]


def all_words(c, keyword=""):
    items, offset = [], 0
    while True:
        params = {"offset": offset, "limit": 100}
        if keyword:
            params["q"] = keyword
        page = c.get("/api/words", params=params).json()
        items += page["items"]
        offset += len(page["items"])
        if not page["has_more"]:
            return page, items


def main():
    r = httpx.get(f"{BASE}/api/words")
    check("未登录返回 401", r.status_code == 401, r.status_code)

    guest = httpx.Client(base_url=BASE, timeout=20)
    reg = guest.post(
        "/api/register",
        json={"account": f"dict_{uuid.uuid4().hex[:8]}", "password": "abc123456", "nickname": "U"},
    )
    guest.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"
    r = guest.get("/api/words")
    code = r.json().get("detail", {}).get("code") if r.status_code == 409 else None
    check("未测用户返回 409 NOT_TESTED", r.status_code == 409 and code == "NOT_TESTED", r.status_code)

    c, _uid = make_user("L1")
    data = c.get("/api/words").json()
    check("默认只返回当前等级", data["level"] == "L1" and all(i["level"] == "L1" for i in data["items"]))
    with SessionLocal() as db:
        expected = db.query(Word).filter(Word.level == "L1").count()
    check("total 等于该等级词数", data["total"] == expected, f"{data['total']} vs {expected}")
    check("默认一页 30 条且还有更多", len(data["items"]) == 30 and data["has_more"] is True, len(data["items"]))

    page2 = c.get("/api/words", params={"offset": 30}).json()
    check(
        "分页不重叠",
        not ({i["id"] for i in data["items"]} & {i["id"] for i in page2["items"]}),
    )

    page, items = all_words(c)
    check("翻页能拿全", len(items) == expected, len(items))
    seen_learned = False
    ordered = True
    for item in items:
        if item["learned"]:
            seen_learned = True
        elif seen_learned:
            ordered = False
            break
    check("未学优先排序", ordered)
    check(
        "每条至少 1 条义项且首条是课本义",
        all(item["senses"] and item["senses"][0]["source"] == "textbook" for item in items),
    )
    check("L1 不下发英文释义", all(item["definition_en"] is None for item in items))

    s = c.get("/api/words", params={"q": "app"}).json()
    check("英文包含搜索命中 apple", any(i["word"].lower() == "apple" for i in s["items"]))
    s = c.get("/api/words", params={"q": "苹果"}).json()
    check("中文释义搜索命中 apple", any(i["word"].lower() == "apple" for i in s["items"]))
    s = c.get("/api/words", params={"q": "APPLE"}).json()
    check("搜索不区分大小写", any(i["word"].lower() == "apple" for i in s["items"]))
    check("搜索结果仍限当前等级", all(i["level"] == "L1" for i in s["items"]))
    s = c.get("/api/words", params={"q": "zzzzzz"}).json()
    check("搜不到时 total=0", s["total"] == 0 and s["items"] == [])

    with SessionLocal() as db:
        only_l3 = db.execute(
            select(Word.word).where(Word.level == "L3").order_by(Word.order_index).limit(50)
        ).scalars().all()
        l1_words = {w.lower() for w in db.execute(select(Word.word).where(Word.level == "L1")).scalars()}
    probe = next((w for w in only_l3 if w.lower() not in l1_words), None)
    if probe:
        s = c.get("/api/words", params={"q": probe}).json()
        check(f"别的等级的词搜不到（{probe}）", s["total"] == 0, s["total"])

    # 已学：答对一道 apple 的题
    apple_qs = questions_for("apple", "L1")
    if apple_qs:
        q = apple_qs[0]
        res = c.post(
            "/api/answer/submit",
            json={"question_id": str(q.id), "answer": str(q.answer), "idempotency_key": uuid.uuid4().hex},
        )
        check("答对 apple 的题目", res.status_code == 200 and res.json()["is_correct"] is True, res.status_code)
        s = c.get("/api/words", params={"q": "apple"}).json()
        item = next((i for i in s["items"] if i["word"].lower() == "apple"), None)
        check("答对过的词标记为已学", bool(item and item["learned"]))
    else:
        check("找到 apple 的题目", False, "无题")

    # 有错题：答错一道 banana 的题
    banana_qs = questions_for("banana", "L1")
    if banana_qs:
        q = banana_qs[0]
        c.post(
            "/api/answer/submit",
            json={"question_id": str(q.id), "answer": "###", "idempotency_key": uuid.uuid4().hex},
        )
        s = c.get("/api/words", params={"q": "banana"}).json()
        item = next((i for i in s["items"] if i["word"].lower() == "banana"), None)
        check("答错过的词标记为有错题", bool(item and item["has_wrong"]))
    else:
        check("找到 banana 的题目", False, "无题")

    # 已学词排到后面
    page, items = all_words(c)
    apple_index = next(i for i, item in enumerate(items) if item["word"].lower() == "apple")
    unlearned_after = [i for i in items[apple_index:] if not i["learned"]]
    check("已学的词排在未学之后", not unlearned_after, len(unlearned_after))

    # L3：英文释义
    c3, _ = make_user("L3")
    page3, items3 = all_words(c3)
    check("L3 只返回 L3 词", all(i["level"] == "L3" for i in items3))
    with_en = [i for i in items3 if i["definition_en"]]
    check("L3 有英文释义", bool(with_en), len(with_en))
    check(
        "L3 英文释义都是英文",
        all(any(ch.isalpha() and ch.isascii() for ch in i["definition_en"]) for i in with_en),
    )

    failed = [name for name, ok in R if not ok]
    print(f"\n{len(R) - len(failed)}/{len(R)} 通过")
    if failed:
        print("失败：" + "；".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
