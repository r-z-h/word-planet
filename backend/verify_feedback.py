"""验证「答错展示义项」：接口要返回正确答案 + 音标 + 全部义项，英文释义只给 L3。"""

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
    acc = f"fb_{uuid.uuid4().hex[:8]}"
    r = c.post("/api/register", json={"account": acc, "password": "abc123456", "nickname": "F"})
    c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    uid = r.json()["user_id"]
    with SessionLocal() as db:
        kp = (
            db.execute(
                select(KnowledgePoint)
                .where(KnowledgePoint.level == level)
                .order_by(KnowledgePoint.sort_order)
            )
            .scalars()
            .first()
        )
        user = db.get(User, uuid.UUID(uid))
        user.level = level
        user.max_level = level
        user.has_tested = True
        progress = db.get(Progress, user.id)
        progress.current_knowledge_point_id = kp.id
        db.commit()
    return c


def pick_question(level, qtype):
    with SessionLocal() as db:
        return (
            db.execute(
                select(Question)
                .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
                .where(KnowledgePoint.level == level, Question.question_type == qtype)
                .order_by(Question.stem)
            )
            .scalars()
            .first()
        )


def word_of(question):
    if question.question_type in ("spelling", "pronunciation"):
        return str(question.answer).strip().lower()
    if isinstance(question.options, dict):
        return str(question.options.get(str(question.answer).upper(), "")).strip().lower()
    return ""


def submit(c, question, answer, key=None):
    return c.post(
        "/api/answer/submit",
        json={
            "question_id": str(question.id),
            "answer": answer,
            "idempotency_key": key or uuid.uuid4().hex,
        },
    ).json()


def expected_word(key):
    with SessionLocal() as db:
        return db.execute(select(Word).where(Word.word == key)).scalar_one_or_none()


def main():
    c = make_user("L1")
    question = pick_question("L1", "word")
    key = word_of(question)
    data = submit(c, question, "###")
    expect = expected_word(key)

    check("答错时返回单词信息", bool(data.get("word")) and data["word"]["word"].lower() == key, data.get("word"))
    check(
        "义项条数与词表一致",
        bool(expect) and len(data["word"]["senses"]) == len(expect.senses),
        f'{len(data["word"]["senses"])} vs {len(expect.senses) if expect else "?"}',
    )
    check("首条义项是课本义", data["word"]["senses"][0]["source"] == "textbook")
    check("音标与词表一致", data["word"]["phonetic"] == (expect.phonetic if expect else None))
    check("answer_text 是正确选项文本", data["answer_text"].lower() == key, data["answer_text"])
    check("L1 不返回英文释义", data["word"]["definition_en"] is None)

    idem = uuid.uuid4().hex
    first = submit(c, question, "###", key=idem)
    second = submit(c, question, "###", key=idem)
    check("幂等重放也带义项", second["duplicated"] and second["word"] and second["word"]["senses"])

    spelling = pick_question("L2", "spelling")
    c2 = make_user("L2")
    data2 = submit(c2, spelling, "###")
    check("拼写题答错也返回义项", bool(data2.get("word")) and bool(data2["word"]["senses"]))
    check("L2 不返回英文释义", data2["word"]["definition_en"] is None)
    check("拼写题 answer_text 是单词", data2["answer_text"].lower() == str(spelling.answer).lower())

    with SessionLocal() as db:
        letter_candidates = (
            db.execute(
                select(Question)
                .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
                .where(KnowledgePoint.level == "L1", Question.question_type == "letter")
            )
            .scalars()
            .all()
        )
        words = {w.lower() for w in db.execute(select(Word.word)).scalars()}
    letter = next((q for q in letter_candidates if word_of(q) not in words), None)
    if letter:
        c3 = make_user("L1")
        data3 = submit(c3, letter, "###")
        check("字母题没有单词信息", data3.get("word") is None)
        check("字母题仍给正确答案文本", data3.get("answer_text") == letter.options[letter.answer])
    else:
        check("找到可测的字母题", False, "无")

    c4 = make_user("L3")
    spelling3 = pick_question("L3", "spelling")
    data4 = submit(c4, spelling3, "###")
    check("L3 返回英文释义", bool(data4.get("word")) and bool(data4["word"]["definition_en"]))
    check(
        "L3 英文释义是多行文本",
        bool(data4["word"]["definition_en"]) and len(data4["word"]["definition_en"]) > 10,
    )

    correct = submit(c, pick_question("L1", "word"), "Z")
    check("答错仍然是 is_correct=false", correct["is_correct"] is False)

    failed = [name for name, ok in R if not ok]
    print(f"\n共 {len(R)} 项，通过 {len(R) - len(failed)}，失败 {len(failed)}")
    if failed:
        print("失败项：" + "；".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
