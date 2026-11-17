"""B 层 RAG 的 LLM 综合 + 降级（全部 mock，不发真实网络）。"""

import app.services.llm as llm_mod
from app.config import settings


def _ask(client, question):
    r = client.post("/api/help/ask", json={"question": question})
    assert r.status_code == 200, r.text
    return r.json()


def test_llm_synthesis_used_when_enabled(l1_client, monkeypatch):
    monkeypatch.setattr(settings, "help_llm_enabled", True)
    monkeypatch.setattr(llm_mod, "is_configured", lambda: True)
    monkeypatch.setattr(
        llm_mod, "chat", lambda messages, **k: "这是 LLM 综合多条资料的回答 [1]"
    )
    data = _ask(l1_client, "每日提醒是自己设置还是自动的，能改时间吗")
    assert data["mode"] == "faq"
    assert "LLM 综合" in data["answer"]
    assert data["sources"]


def test_llm_failure_falls_back_to_extractive(l1_client, monkeypatch):
    monkeypatch.setattr(settings, "help_llm_enabled", True)
    monkeypatch.setattr(llm_mod, "is_configured", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(llm_mod, "chat", boom)
    data = _ask(l1_client, "什么是满套？")
    assert data["mode"] == "faq"
    assert "满套" in data["answer"]  # 退回原文片段


def test_llm_disabled_uses_extractive(l1_client, monkeypatch):
    monkeypatch.setattr(settings, "help_llm_enabled", False)

    def explode(*a, **k):
        raise AssertionError("LLM 不应被调用")

    monkeypatch.setattr(llm_mod, "chat", explode)
    data = _ask(l1_client, "什么是满套？")
    assert data["mode"] == "faq" and "满套" in data["answer"]
