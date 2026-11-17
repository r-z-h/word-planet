"""B 层（独立 RAG 引擎 rag_kb）：检索命中 + 拒答 + A 优先。"""


def _ask(client, question, context=None):
    body = {"question": question}
    if context is not None:
        body["context"] = context
    r = client.post("/api/help/ask", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_rule_layer_still_wins(l1_client):
    data = _ask(l1_client, "花、星、徽记怎么换？")
    assert data["mode"] == "rule"


def test_kb_hit_returns_answer_and_source(l1_client):
    data = _ask(l1_client, "什么是满套？")
    assert data["mode"] == "faq"
    assert data["sources"]
    assert "满套" in data["answer"]


def test_kb_multi_chunk_reminder(l1_client):
    data = _ask(l1_client, "每日提醒是自己设置还是自动的，能改时间吗")
    assert data["mode"] == "faq"
    assert data["sources"]
    assert ("自动" in data["answer"]) or ("设置" in data["answer"])


def test_kb_refuses_unrelated(l1_client):
    data = _ask(l1_client, "今天天气怎么样？")
    assert data["mode"] == "refuse"
