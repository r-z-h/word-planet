"""从现成英中句对语料（Tatoeba/ManyThings, CC BY 2.0）为「听力理解」筛题。

严格正确性校验（不放错误信息进题库）：
- 句子只能来自语料原文，不改写。
- 每个英文单词必须在 ECDICT 词典里（或为句中大写专有名词/常见缩写被排除/缩写词排除）。
- 排除缩写词（Mr./Dr./etc. 等 TTS 易读错）。
- 正确答案 = 句子里出现的一个 L3 词表单词；且**不能是同形异音词**（read/live/wind/lead/close/tear/bow…），
  避免"听到的发音"和"选项拼写"对不上。
- 干扰项 = 其它 L3 单词，且整词/子串都不在句中。
- 每套 15 题，生成第 2..15 套（第 1 套 seed.py 手写）；幂等。
"""

import csv
import json
import random
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models import Attempt, KnowledgePoint, Question, WrongQuestion

ROOT = Path(__file__).resolve().parents[1]
WORDS = ROOT / "data" / "build" / "words.json"
CORPUS = ROOT / "data" / "sources" / "manythings" / "cmn.txt"
ECDICT = ROOT / "data" / "sources" / "ecdict-repo" / "ecdict.csv"

SET_SIZE = 15
FIRST_SET = 2
SETS = 14
NEED = SET_SIZE * SETS

KEYS = ["A", "B", "C", "D"]
LEVEL = "L3"

STOP = set(
    "the a an is are am was were be been being do does did to of in on at by for with and or "
    "but if then this that these those i you he she it we they my your his her its our their "
    "me him us them not no yes there here have has had can will would should could may might "
    "must very just now so as what which who whom whose when where why how some any many much "
    "more most each every either neither both all none few little other another such same own "
    "out up down off over about into from than too also only even still yet ever never always "
    "because while during before after above below between under again once".split()
)

# 同形异音词（拼写相同、不同语境发音不同）——不作听力答案，避免发音/拼写错配
HETERONYMS = set(
    "read live wind lead close tear bow row use minute present object record produce desert "
    "content refuse wound bass dove sow excuse house invalid subject project contract conduct "
    "contest convert digest entrance incense insult permit polish rebel resume separate "
    "alternate appropriate delegate estimate graduate intimate moderate predicate dove".split()
)

ABBREV = set(
    "mr mrs ms dr st jr sr etc vs pm am usa uk ok tv dvd cd".split()
)

ALLOWED = re.compile(r"^[A-Za-z ,.'!?\-]+$")
TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

_vocab_cache = None


def load_vocab():
    global _vocab_cache
    if _vocab_cache is not None:
        return _vocab_cache
    vocab = set()
    try:
        with ECDICT.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    vocab.add(row[0].strip().lower())
    except FileNotFoundError:
        print("警告：找不到 ECDICT，跳过逐词校验")
    _vocab_cache = vocab
    print(f"ECDICT 词表：{len(vocab)}")
    return vocab


def load_target_words():
    data = json.loads(WORDS.read_text(encoding="utf-8"))
    out = {}
    for w in data.get(LEVEL, {}).get("words", []):
        word = w["word"].strip()
        if not re.fullmatch(r"[A-Za-z]+", word) or len(word) < 3:
            continue
        key = word.lower()
        if key in STOP:
            continue
        out.setdefault(key, w.get("meaning", ""))
    return out


def tokens_ok(toks, vocab):
    """逐词校验：小写词必须在词典；大写视为专有名词放行；排除缩写。"""
    if not vocab:
        return True
    for t in toks:
        low = t.lower()
        if low in ABBREV:
            return False
        if t[:1].isupper():
            continue  # 专有名词 / 句首
        if re.fullmatch(r"[a-z]+('[a-z]+)?", low):
            base = low.split("'")[0]
            if base in vocab:
                continue
            if len(base) == 1 and base in ("i", "a"):
                continue
            return False
    return True


def build_candidates(l3, vocab):
    seen = set()
    out = []
    rejected_unknown = rejected_abbrev = rejected_heter = 0
    for line in CORPUS.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        en = parts[0].strip()
        if not en or not ALLOWED.match(en):
            continue
        if not (12 <= len(en) <= 55):
            continue
        toks = TOKEN.findall(en)
        if not (3 <= len(toks) <= 8):
            continue
        if en in seen:
            continue
        if any(t.lower() in ABBREV for t in toks):
            rejected_abbrev += 1
            continue
        if not tokens_ok(toks, vocab):
            rejected_unknown += 1
            continue
        cands = []
        for pos_i, t in enumerate(toks):
            tl = t.lower()
            if "'" in tl or tl not in l3 or tl in STOP:
                continue
            if t[:1].isupper():
                continue
            if tl in HETERONYMS:
                rejected_heter += 1
                continue
            cands.append(t)
        if not cands:
            continue
        target_tok = max(cands, key=len)
        target = target_tok.lower()
        seen.add(en)
        out.append((en, target, l3[target]))
    print(f"候选句子 {len(out)}（排除：生僻/拼写可疑 {rejected_unknown}，缩写 {rejected_abbrev}，同形异音 {rejected_heter}）")
    return out


def pick_distractors(en, target, l3_keys, rng):
    low = en.lower()
    picks = []
    pool = list(l3_keys)
    rng.shuffle(pool)
    for k in pool:
        if k == target or k in low:
            continue
        picks.append(k)
        if len(picks) == 3:
            break
    return picks


def main():
    vocab = load_vocab()
    l3 = load_target_words()
    candidates = build_candidates(l3, vocab)

    rng = random.Random(20261105)
    rng.shuffle(candidates)

    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.level == LEVEL, KnowledgePoint.sort_order == 1
            )
        ).scalar_one_or_none()
        if kp is None:
            print("找不到 L3 听力理解知识点")
            return

        old = db.execute(
            select(Question).where(
                Question.knowledge_point_id == kp.id, Question.set_no >= FIRST_SET
            )
        ).scalars().all()
        removed = 0
        for q in old:
            used = db.execute(select(Attempt.id).where(Attempt.question_id == q.id).limit(1)).first()
            wrong = db.execute(
                select(WrongQuestion.id).where(WrongQuestion.question_id == q.id).limit(1)
            ).first()
            if used or wrong:
                continue
            db.delete(q)
            removed += 1
        db.commit()
        if removed:
            print(f"已删除旧生成题 {removed} 道")

        existing = set(
            db.execute(select(Question.stem).where(Question.knowledge_point_id == kp.id)).scalars()
        )

        l3_keys = sorted(l3.keys())
        rows = []
        per_target: dict[str, int] = {}
        idx = 0
        for en, target, meaning in candidates:
            if len(rows) >= NEED:
                break
            if en in existing:
                continue
            if per_target.get(target, 0) >= 2:
                continue
            distractors = pick_distractors(en, target, l3_keys, random.Random(hash(en) & 0xFFFFFFFF))
            if len(distractors) < 3:
                continue
            pos = (idx + len(target)) % 4
            opts = list(distractors)
            opts.insert(pos, target)
            options = {KEYS[i]: opts[i] for i in range(4)}
            answer = KEYS[pos]
            set_no = FIRST_SET + idx // SET_SIZE
            explanation = f"你听到的句子是「{en}」。句子里出现的词是 {target}。"
            rows.append(
                {
                    "knowledge_point_id": kp.id,
                    "question_type": "listening",
                    "stem": en,
                    "options": options,
                    "answer": answer,
                    "difficulty": 3,
                    "set_no": set_no,
                    "explanation": explanation,
                }
            )
            existing.add(en)
            per_target[target] = per_target.get(target, 0) + 1
            idx += 1

        if len(rows) < NEED:
            print(f"警告：只凑到 {len(rows)} 题（目标 {NEED}）")
        if rows:
            db.execute(
                pg_insert(Question)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["knowledge_point_id", "stem"])
            )
            db.commit()
        sets = sorted({r["set_no"] for r in rows})
        print(f"听力生成 {len(rows)} 题 / {len(sets)} 套" + (f"（第 {sets[0]}–{sets[-1]} 套）" if sets else ""))


if __name__ == "__main__":
    main()
