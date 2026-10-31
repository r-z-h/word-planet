"""拼写题字母砖：生成规则 + 接口下发。"""

import uuid
from collections import Counter

from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint, Progress, User
from app.services.tiles import tiles_for


def test_tiles_are_deterministic():
    qid = uuid.uuid4()
    a = tiles_for(qid, "banana")
    b = tiles_for(qid, "banana")
    assert a == b  # 同一题顺序稳定


def test_tiles_cover_answer_letters_and_have_four_distractors():
    for word in ["apple", "banana", "book", "school", "communication", "every"]:
        tiles = tiles_for(uuid.uuid4(), word)
        uniq = sorted(set(word.lower()))
        # 每个不同字母各 1 块
        assert sorted(c for c in tiles if c in uniq) == uniq
        # 总块数 = 不同字母数 + 4
        assert len(tiles) == len(uniq) + 4
        # 没有重复砖
        assert len(set(tiles)) == len(tiles)
        # 干扰字母不在答案里
        assert all(c not in uniq for c in tiles if c not in uniq)


def _force_kp(user_id: str, level: str, qtype: str) -> str:
    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.level == level, KnowledgePoint.question_type == qtype
            ).order_by(KnowledgePoint.sort_order)
        ).scalars().first()
        assert kp is not None, f"找不到 {level}/{qtype} 知识点"
        user = db.get(User, uuid.UUID(user_id))
        user.level = level
        user.max_level = level
        user.has_tested = True
        prog = db.get(Progress, user.id)
        prog.current_knowledge_point_id = kp.id
        prog.last_question_id = None
        db.commit()
        return str(kp.id)


def test_spelling_question_returns_tiles(user_client):
    _force_kp(user_client.user_id, "L2", "spelling")
    resp = user_client.get("/api/question/next")
    assert resp.status_code == 200, resp.text
    q = resp.json()["question"]
    assert q["question_type"] == "spelling"
    assert q["tiles"] and len(q["tiles"]) >= 5
    assert all(len(c) == 1 for c in q["tiles"])


def test_choice_question_has_no_tiles(l1_client):
    resp = l1_client.get("/api/question/next")
    assert resp.status_code == 200, resp.text
    q = resp.json()["question"]
    assert q["question_type"] in ("letter", "word")
    assert q.get("tiles") is None
