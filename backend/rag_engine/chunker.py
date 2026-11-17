"""把 Markdown 帮助文章切成检索用的"片段(chunk)"。

规则：按 `## 小标题` 分段；每段内按空行分自然段，累积到 max_chars 就切一块。
每块带：id / doc_id / doc_title / section / text / source_path。
"""

from __future__ import annotations

import re
from pathlib import Path


def _split_sections(md: str) -> tuple[str, list[tuple[str, str]]]:
    lines = md.splitlines()
    title = ""
    sections: list[tuple[str, str]] = []
    cur = None
    buf: list[str] = []
    for ln in lines:
        if ln.startswith("# ") and not title:
            title = ln[2:].strip()
            continue
        if ln.startswith("## "):
            if cur is not None:
                sections.append((cur, "\n".join(buf).strip()))
            cur = ln[3:].strip()
            buf = []
        else:
            buf.append(ln)
    if cur is not None:
        sections.append((cur, "\n".join(buf).strip()))
    return title, sections


def _mk(path: Path, title: str, section: str, text: str, idx: int) -> dict:
    return {
        "id": f"{path.stem}::{section}::{idx}",
        "doc_id": path.stem,
        "doc_title": title or path.stem,
        "section": section,
        "text": text.strip(),
        "source_path": "/help",
    }


def chunk_articles(kb_dir: Path, max_chars: int = 450) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(Path(kb_dir).glob("*.md")):
        title, sections = _split_sections(path.read_text(encoding="utf-8"))
        for sec_title, body in sections:
            body = re.sub(r"\n{3,}", "\n\n", body).strip()
            if not body:
                continue
            paras = [p.strip() for p in body.split("\n\n") if p.strip()]
            cur = ""
            idx = 0
            for p in paras:
                if cur and len(cur) + len(p) + 2 > max_chars:
                    chunks.append(_mk(path, title, sec_title, cur, idx))
                    idx += 1
                    cur = p
                else:
                    cur = (cur + "\n\n" + p) if cur else p
            if cur:
                chunks.append(_mk(path, title, sec_title, cur, idx))
    return chunks
