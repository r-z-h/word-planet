"""RAG 引擎：切块 → 嵌入 → 索引 → (向量+关键词)混合检索 → 传入 LLM 生成 / 抽取兜底。

设计要点（业务级）：
- 独立模块：不 import app / 数据库 / 说明书；只吃 `rag_kb/articles/*.md`。
- 混合检索：最终分 = 0.8 * 余弦相似度 + 0.2 * 关键词覆盖率（中文二元组）。
- 生成：由调用方传入 `chat(messages)->str`（这样引擎不绑定具体 LLM 供应商）；
  不传则退化为"返回最相关片段原文"（抽取式，零 LLM）。
- 引用：返回 chunks 带编号 n，LLM 用 [n] 引用；sources 由引擎按顺序给出。
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
from pathlib import Path

from .chunker import chunk_articles
from .embedder import Embedder

# backend/rag_engine/engine.py -> parents[2] 是仓库根
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KB_DIR = ROOT / "rag_kb" / "articles"
DEFAULT_MODEL_DIR = ROOT / "data" / "models" / "bge-small-zh-v1.5"
DEFAULT_INDEX = ROOT / "rag_kb" / "index.json"

INDEX_VERSION = "kb-bge-v1"
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
MIN_SCORE = 0.40  # 混合分阈值（低于视为没命中）；真实命中≥0.47，无关≤0.38
COS_WEIGHT = 0.8
KW_WEIGHT = 0.2
LLM_DEADLINE = 8.0  # LLM 最长墙钟秒数，超时立刻退回原文（防 DeepSeek 偶发长卡）

_LLM_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)
_ANSWER_CACHE: dict[tuple, tuple[float, dict]] = {}
CACHE_TTL = 600  # 同问秒回：缓存 10 分钟


def _bigrams(text: str) -> set[str]:
    t = re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9]", "", (text or "").lower())
    grams = {t[i : i + 2] for i in range(len(t) - 1)}
    grams |= set(t)
    return grams


def _keyword_score(question: str, text: str) -> float:
    """问题里的二元组有多大比例出现在片段里（0~1）。"""
    q = _bigrams(question)
    if not q:
        return 0.0
    d = _bigrams(text)
    return len(q & d) / len(q)


def build_messages(question: str, chunks: list[dict]) -> list[dict]:
    system = (
        "你是 Word Planet 学习平台的站内帮助助手。规则："
        "1) 只能依据【资料】回答；2) 可以综合多条资料；"
        "3) 用中文、简短、亲切的少儿口吻；"
        "4) 在相应句子后用 [1][2] 这样的编号标注引用了第几条资料；"
        "5) 资料不足以回答时，直接说“这个我暂时答不上来，可以到对应页面看看”，不要编造。"
    )
    material = "\n\n".join(
        f"[{c['n']}] 《{c['title']} · {c['section']}》\n{c['text']}" for c in chunks
    )
    user = f"【资料】\n{material}\n\n【问题】\n{question}\n\n请综合资料用一两句话回答，并用[n]标注引用。"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class RagEngine:
    def __init__(self, kb_dir=None, model_dir=None, index_path=None):
        self.kb_dir = Path(kb_dir or DEFAULT_KB_DIR)
        self.model_dir = Path(model_dir or DEFAULT_MODEL_DIR)
        self.index_path = Path(index_path or DEFAULT_INDEX)
        self.embedder = Embedder(self.model_dir)
        self._chunks: list[dict] | None = None
        self._mtime: float | None = None

    # ---------------- 建索引 ----------------
    def build(self) -> dict:
        chunks = chunk_articles(self.kb_dir)
        vecs = self.embedder.encode([c["text"] for c in chunks], prefix="")
        for c, v in zip(chunks, vecs):
            c["vec"] = v
        data = {
            "version": INDEX_VERSION,
            "model": self.model_dir.name,
            "dim": self.embedder.dim() if chunks else 0,
            "count": len(chunks),
            "chunks": chunks,
        }
        self.index_path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        self._chunks = chunks
        try:
            self._mtime = self.index_path.stat().st_mtime
        except OSError:
            self._mtime = None
        return data

    def _load(self) -> None:
        # 热加载：索引文件被重建（mtime 变化）→ 重新读取，无需重启后端
        try:
            mtime = self.index_path.stat().st_mtime if self.index_path.exists() else None
        except OSError:
            mtime = None
        if self._chunks is not None and mtime is not None and mtime == self._mtime:
            return
        if self.index_path.exists():
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if data.get("version") == INDEX_VERSION:
                self._chunks = data["chunks"]
                self._mtime = mtime
                return
        self.build()

    def warmup(self) -> None:
        self._load()
        self.embedder.encode(["预热"], prefix="")

    # ---------------- 检索 + 生成 ----------------
    def query(self, question: str, chat=None, top_k: int = 5, min_score: float = MIN_SCORE):
        self._load()
        # 同问缓存（仅 LLM 模式）：同一问题在索引未变时直接复用
        cache_key = None
        if chat is not None:
            cache_key = (question.strip().lower(), INDEX_VERSION, self._mtime)
            hit = _ANSWER_CACHE.get(cache_key)
            if hit and hit[0] > time.time():
                return {**hit[1], "cached": True}
        qv = self.embedder.encode([question], prefix=QUERY_PREFIX)[0]
        scored = []
        for c in self._chunks:
            cos = sum(a * b for a, b in zip(qv, c["vec"]))
            kw = _keyword_score(question, c["text"])
            score = COS_WEIGHT * cos + KW_WEIGHT * kw
            scored.append((score, cos, kw, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: max(1, top_k)]
        best_score = top[0][0]
        if best_score < min_score:
            return None

        chunks = [
            {
                "n": i + 1,
                "title": c["doc_title"],
                "section": c["section"],
                "text": c["text"],
                "score": round(s, 4),
                "cos": round(cos, 4),
                "kw": round(kw, 4),
            }
            for i, (s, cos, kw, c) in enumerate(top)
        ]

        if chat is not None:
            try:
                # 只把最相关的前 3 段喂给模型；墙钟死线 8s，超时退回原文
                fut = _LLM_POOL.submit(chat, build_messages(question, chunks[:3]))
                answer = str(fut.result(timeout=LLM_DEADLINE)).strip()
                used_llm = True
            except Exception:  # LLM 失败/超时 → 退回最相关片段原文，保证可用
                answer = chunks[0]["text"]
                used_llm = False
        else:
            answer = chunks[0]["text"]
            used_llm = False

        # 出处只列"答案里真正引用到的"片段（按 [n] 解析）；抽取式则默认第 1 段
        if used_llm:
            nums = sorted(
                {int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= len(chunks)}
            )
        else:
            nums = [1]
        if not nums:
            nums = [1]
        sources, seen = [], set()
        for n in nums:
            ch = chunks[n - 1]
            key = (ch["title"], ch["section"])
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {"title": f"{ch['title']} · {ch['section']}", "path": "/help"}
            )

        # 引用编号只用于溯源，展示前从回答文本里去掉（出处由 sources 给出）
        if used_llm:
            answer = re.sub(r"\s*\[\d+\]", "", answer)
            answer = re.sub(r"\s+([，。！？、；：])", r"\1", answer).strip()

        result = {
            "answer": answer,
            "sources": sources,
            "used_llm": used_llm,
            "score": round(best_score, 4),
            "chunks": chunks,
        }
        if cache_key is not None and used_llm:
            _ANSWER_CACHE[cache_key] = (time.time() + CACHE_TTL, result)
        return result
