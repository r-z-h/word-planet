"""系统问答助手（Phase A）回归：断言答案里的数字与库/常量一致。

跑法（backend 目录）：
    .\\.venv\\Scripts\\python.exe -m pytest tests/test_help.py -q
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint


def _ask(client, question, context=None):
    body = {"question": question}
    if context is not None:
        body["context"] = context
    r = client.post("/api/help/ask", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_capability_lists_gate_and_numbers(l1_client):
    data = _ask(l1_client, "我怎么才能做能力测试？")
    assert data["mode"] == "rule"
    assert "能力测试" in data["answer"]
    assert "基础问候词" in data["answer"]
    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint).where(KnowledgePoint.name == "基础问候词")
        ).scalar_one()
        need = kp.gate_required
    # 新用户 0 枚徽记 → 还差 need 枚（数字与 DB 一致）
    assert f"还差 {need} 枚" in data["answer"]
    assert data["sources"]


def test_test_pass(l1_client):
    data = _ask(l1_client, "能力测试几题算通过？")
    assert data["mode"] == "rule"
    assert "8" in data["answer"] and "10" in data["answer"]


def test_exchange_constants(l1_client):
    data = _ask(l1_client, "花、星、徽记怎么兑换？")
    assert data["mode"] == "rule"
    assert "3" in data["answer"] and "5" in data["answer"]
    assert "兑换" in data["answer"]


def test_planet_medal_multiturn(l1_client):
    first = _ask(l1_client, "破壳蛋徽记怎么拿？")
    assert first["mode"] == "rule" and "破壳蛋" in first["answer"]
    ctx = first["context"]
    second = _ask(l1_client, "那我还差几枚？", context=ctx)
    assert second["mode"] == "rule"
    assert "还差" in second["answer"]


def test_daily_task(l1_client):
    data = _ask(l1_client, "今天任务完成了吗？")
    assert data["mode"] == "rule" and "任务" in data["answer"]


def test_badge_generic_distinguishes_two_kinds(l1_client):
    data = _ask(l1_client, "徽章怎么解锁？")
    assert data["mode"] == "rule"
    assert "成就" in data["answer"] and "徽记" in data["answer"]


def test_mastery(l1_client):
    data = _ask(l1_client, "错题要连对几次才补花？")
    assert data["mode"] == "rule" and "3" in data["answer"] and "10" in data["answer"]


def test_refuse_out_of_scope(l1_client):
    data = _ask(l1_client, "今天天气怎么样？")
    assert data["mode"] == "refuse"
    assert "不在提问范围内" in data["answer"]
    assert data["suggestions"]


def test_unknown_after_known_does_not_inherit_prev_intent(l1_client):
    """回归：上一轮问过兑换，再问一个不认识的问题，不能被旧意图顶替。"""
    exchange = _ask(l1_client, "花、星、徽记怎么换？")
    assert exchange["mode"] == "rule" and exchange["context"]["last_intent"] == "exchange"
    data = _ask(l1_client, "今天天气怎么样？", context=exchange["context"])
    assert data["mode"] == "refuse"
    assert "三层奖励" not in data["answer"]


def test_kp_question_count_after_exchange(l1_client):
    """回归：问'简单拼写有多少题'应答题量，不能复用兑换答案。"""
    exchange = _ask(l1_client, "花、星、徽记怎么换？")
    data = _ask(l1_client, "简单拼写到底有多少题目", context=exchange["context"])
    assert data["mode"] == "rule"
    assert "简单拼写" in data["answer"]
    assert "套" in data["answer"]
    assert "三层奖励" not in data["answer"]


def test_followup_still_works(l1_client):
    """正常的追问仍要继承（不能因为修 bug 把多轮修死）。"""
    first = _ask(l1_client, "破壳蛋徽记怎么拿？")
    second = _ask(l1_client, "那我还差几枚？", context=first["context"])
    assert second["mode"] == "rule" and "还差" in second["answer"]


def test_weekday_not_treated_as_followup(l1_client):
    """回归：'今天你星期几' 不能被当成上一轮的追问而重复答案。"""
    first = _ask(l1_client, "怎么做能力测试？")
    assert first["context"]["last_intent"] == "capability_test"
    data = _ask(l1_client, "今天你星期几", context=first["context"])
    assert "本级门槛已全部达标" not in data["answer"]
    assert "10 题答对 8" not in data["answer"]


def test_exception_fallback(l1_client, monkeypatch):
    """任何查询抛异常都要降级成友好提示，不能 500。"""
    import app.services.help as help_mod

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(help_mod, "_ans_mastery", boom)
    data = _ask(l1_client, "错题要连对几次才补花？")
    assert data["mode"] == "refuse"
    assert "小状况" in data["answer"]

