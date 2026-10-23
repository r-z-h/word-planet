"""把 data/build/words.json 生成成题目，每 15 词一套写入数据库。

规则：
- 第 1 套是手写的高质量题（seed.py 生成），这里从第 2 套开始追加。
- 拼写 / 跟读只用纯字母单词，词组跳过。
- 同义词（中文释义相同）会导致题干重复，按释义去重，保证每套正好 15 题。
- 幂等：重跑前先删掉本脚本生成的旧题（set_no >= 2 且无人作答）。
"""

import json
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models import Attempt, KnowledgePoint, Question

ROOT = Path(__file__).resolve().parents[1]
WORDS = ROOT / "data" / "build" / "words.json"

SET_SIZE = 15
FIRST_GENERATED_SET = 2

TARGETS = [
    (("L1", 2), "L1", "word"),
    (("L2", 1), "L2", "word"),
    (("L2", 2), "L2", "spelling"),
    (("L2", 3), "L2", "pronunciation"),
    (("L3", 2), "L3", "spelling"),
]

KEYS = ["A", "B", "C", "D"]
DIFFICULTY = {"L1": 1, "L2": 2, "L3": 3}


def stem_of(word: str, meaning: str, qtype: str) -> str:
    if qtype == "word":
        return f"“{meaning}”用英语怎么说？"
    if qtype == "spelling":
        return f"“{meaning}”怎么拼写？"
    return word


def pick_candidates(words, qtype, existing_stems):
    """过滤 + 按题干去重，并避开第 1 套已有的题干，保证每套正好 15 题。"""
    out = []
    seen = set()
    for w in words:
        word = w["word"]
        if qtype in ("spelling", "pronunciation"):
            if " " in word or not word.isalpha():
                continue
        # 题干用的是哪个字段，就用哪个字段去重
        key = word.lower() if qtype == "pronunciation" else w["meaning"]
        if key in seen:
            continue
        if stem_of(word, w["meaning"], qtype) in existing_stems:
            continue
        seen.add(key)
        out.append(w)
    return out


def make_options(correct, pool, offset):
    distractors = []
    idx = offset
    while len(distractors) < 3 and idx < offset + len(pool) * 2:
        candidate = pool[idx % len(pool)]
        idx += 1
        if candidate != correct and candidate not in distractors:
            distractors.append(candidate)
    while len(distractors) < 3:  # 极端兜底
        distractors.append(f"word{len(distractors)}")
    pos = (offset + len(correct)) % 4
    options = list(distractors)
    options.insert(pos, correct)
    return {KEYS[i]: options[i] for i in range(4)}, KEYS[pos]


def build_rows(kp_id, candidates, qtype, difficulty):
    pool = [w["word"] for w in candidates]
    chunks = [candidates[i : i + SET_SIZE] for i in range(0, len(candidates), SET_SIZE)]
    chunks = [c for c in chunks if len(c) == SET_SIZE]

    rows = []
    for ci, chunk in enumerate(chunks):
        set_no = FIRST_GENERATED_SET + ci
        for wi, item in enumerate(chunk):
            word, meaning = item["word"], item["meaning"]

            if qtype == "word":
                options, answer = make_options(word, pool, ci * SET_SIZE + wi)
                rows.append(dict(
                    knowledge_point_id=kp_id, question_type="word",
                    stem=f"“{meaning}”用英语怎么说？", options=options, answer=answer,
                    explanation=f"“{meaning}”的英文是 {word}。",
                    difficulty=difficulty, set_no=set_no,
                ))
            elif qtype == "spelling":
                rows.append(dict(
                    knowledge_point_id=kp_id, question_type="spelling",
                    stem=f"“{meaning}”怎么拼写？", options=None, answer=word,
                    explanation=f"“{meaning}”是 {word}，共 {len(word)} 个字母：{' '.join(word)}。",
                    difficulty=difficulty, set_no=set_no,
                ))
            else:
                rows.append(dict(
                    knowledge_point_id=kp_id, question_type="pronunciation",
                    stem=word, options=None, answer=word,
                    explanation=f"{word}（{meaning}）。先听标准音，再跟读一遍。",
                    difficulty=difficulty, set_no=set_no,
                ))
    return rows


def main():
    data = json.loads(WORDS.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        total = 0
        for (kp_level, kp_order), word_level, qtype in TARGETS:
            kp = db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.level == kp_level, KnowledgePoint.sort_order == kp_order
                )
            ).scalar_one_or_none()
            if kp is None:
                print(f"跳过：找不到知识点 {kp_level}-{kp_order}")
                continue

            # 先清掉本脚本上次生成的题（有作答记录的不动）
            old_ids = db.execute(                select(Question.id).where(
                    Question.knowledge_point_id == kp.id, Question.set_no >= FIRST_GENERATED_SET
                )
            ).scalars().all()
            if old_ids:
                used = db.execute(
                    select(func.count()).select_from(Attempt).where(Attempt.question_id.in_(old_ids))
                ).scalar_one()
                if used:
                    print(f"{kp.name}: 有 {used} 条作答记录，跳过重建")
                    continue
                db.execute(delete(Question).where(Question.id.in_(old_ids)))
                db.commit()

            existing_stems = set(
                db.execute(
                    select(Question.stem).where(Question.knowledge_point_id == kp.id)
                ).scalars()
            )
            candidates = pick_candidates(
                data[word_level]["words"], qtype, existing_stems
            )
            rows = build_rows(kp.id, candidates, qtype, DIFFICULTY[kp_level])
            if not rows:
                print(f"{kp.name}: 没有可生成的题")
                continue

            stmt = pg_insert(Question).values(rows).on_conflict_do_nothing(
                index_elements=["knowledge_point_id", "stem"]
            )
            db.execute(stmt)
            db.commit()

            sets = sorted({r["set_no"] for r in rows})
            total += len(rows)
            print(
                f"{kp_level} {kp.name}({qtype}): {len(rows)} 题 / {len(sets)} 套 "
                f"(第 {sets[0]}–{sets[-1]} 套)，候选词 {len(candidates)}"
            )

        print(f"\n本次生成题目：{total}")


if __name__ == "__main__":
    main()
