import os
import uuid
from pathlib import Path

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent
_base_url = os.environ.get("DATABASE_URL") or dotenv_values(BASE_DIR / ".env").get("DATABASE_URL")
if not _base_url:
    raise RuntimeError("找不到 DATABASE_URL，请先配置 backend/.env")

# 测试库：与业务库同实例、不同 database，避免污染真实数据
os.environ["DATABASE_URL"] = _base_url.rsplit("/", 1)[0] + "/word_planet_test"
os.environ["ENABLE_SCHEDULER"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import KnowledgePoint, Progress, Question, User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def prepared_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from seed import seed

    seed()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def user_client(client):
    account = f"t_{uuid.uuid4().hex[:10]}"
    resp = client.post(
        "/api/register",
        json={"account": account, "password": "abc123456", "nickname": "测试娃"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    client.account = account
    client.user_id = resp.json()["user_id"]
    return client


def answer_of(question_id: str) -> str:
    with SessionLocal() as db:
        return str(db.get(Question, uuid.UUID(question_id)).answer)


def force_level(user_id: str, level: str) -> str:
    """把用户直接放到指定等级的第一个知识点，返回知识点 id。"""
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
        user = db.get(User, uuid.UUID(user_id))
        user.level = level
        user.has_tested = True
        progress = db.get(Progress, user.id)
        progress.current_knowledge_point_id = kp.id
        db.commit()
        return str(kp.id)


def complete_current_kp(client, limit: int = 40) -> bool:
    """一直答对，直到知识点完成。"""
    for _ in range(limit):
        resp = client.get("/api/question/next")
        if resp.status_code != 200:
            return False
        q = resp.json()["question"]
        res = client.post(
            "/api/answer/submit",
            json={
                "question_id": q["id"],
                "answer": answer_of(q["id"]),
                "idempotency_key": uuid.uuid4().hex,
            },
        )
        assert res.status_code == 200, res.text
        if res.json()["progress_advanced"]:
            return True
    return False


@pytest.fixture()
def l1_client(user_client):
    force_level(user_client.user_id, "L1")
    return user_client
