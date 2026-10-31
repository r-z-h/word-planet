"""拼写题的字母砖生成。

规则（见 docs/玩法设计.md 6.2 / 第 9 章）：
- 砖池 = 答案中**每个不同字母各 1 块**（小写去重）
- 另加 4 个干扰字母（答案里没有的），各 1 块
- 打乱顺序要**稳定**：同一道题重进顺序一致，所以用 question.id 做种子

不做成数据库列，避免改题库；纯函数、可重复。
"""

import hashlib
import random
import string
import uuid

DISTRACTOR_COUNT = 4


def _seed(question_id: uuid.UUID | str, answer: str) -> int:
    raw = f"{question_id}:{answer.lower()}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def tiles_for(question_id: uuid.UUID | str, answer: str) -> list[str]:
    """返回打乱后的字母砖（含重复结构的答案字母 + 干扰字母）。"""
    word = (answer or "").strip().lower()
    if not word:
        return []

    uniq: list[str] = []
    for ch in word:
        if ch.isalpha() and ch not in uniq:
            uniq.append(ch)

    pool = list(string.ascii_lowercase)
    rng = random.Random(_seed(question_id, word))
    candidates = [c for c in pool if c not in uniq]
    rng.shuffle(candidates)
    distractors = candidates[:DISTRACTOR_COUNT]

    tiles = uniq + distractors
    rng.shuffle(tiles)
    return tiles
