"""跟读接口：返回套信息与音标字段。"""

import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint, Progress, User


def _force_kp(user_id: str, level: str, qtype: str) -> str:
    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.level == level, KnowledgePoint.question_type == qtype)
            .order_by(KnowledgePoint.sort_order)
        ).scalars().first()
        user = db.get(User, uuid.UUID(user_id))
        user.level = level
        user.max_level = level
        user.has_tested = True
        prog = db.get(Progress, user.id)
        prog.current_knowledge_point_id = kp.id
        prog.last_question_id = None
        db.commit()
        return str(kp.id)


def test_pronunciation_next_returns_set_info(user_client):
    _force_kp(user_client.user_id, "L2", "pronunciation")
    resp = user_client.get("/api/pronunciation/next")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["set_no"] == 1
    assert data["set_total"] > 0
    assert data["set_done"] == 0
    q = data["question"]
    assert q["answer"] and q["stem"]
    assert "phonetic" in q
