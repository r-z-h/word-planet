"""运维能力：未命中问题日志 + 重建索引热加载。"""


def test_unmatched_question_is_logged(l1_client):
    from app.services import help as help_service

    log = help_service._UNMATCHED_LOG
    before = log.read_text(encoding="utf-8") if log.exists() else ""

    r = l1_client.post("/api/help/ask", json={"question": "给我讲个笑话"})
    assert r.status_code == 200
    assert r.json()["mode"] == "refuse"

    after = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "讲个笑话" in after and len(after) > len(before)


def test_reindex_hot_reloads_engine():
    import rag_engine

    engine = rag_engine.get_engine()
    data = rag_engine.build_index()
    assert data["count"] > 0
    # build 后同一进程内 _chunks 立即更新（热加载）
    assert engine._chunks is not None
    assert len(engine._chunks) == data["count"]
