"""rag_engine 对外入口（独立模块）。

主项目只调 `query(question, chat=...)` / `warmup()` / `build_index()`，不感知内部。
"""

from __future__ import annotations

from .engine import (
    DEFAULT_INDEX,
    DEFAULT_KB_DIR,
    DEFAULT_MODEL_DIR,
    RagEngine,
    build_messages,
)

_engine: RagEngine | None = None


def get_engine() -> RagEngine:
    global _engine
    if _engine is None:
        _engine = RagEngine()
    return _engine


def query(question: str, chat=None, **kwargs):
    return get_engine().query(question, chat=chat, **kwargs)


def warmup() -> None:
    get_engine().warmup()


def build_index() -> dict:
    return get_engine().build()
