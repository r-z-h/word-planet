"""把人教版分年级词表导入为项目知识库。

输入：data/sources/kylebing/*.jsonl（KyleBing/english-vocabulary，BSD-3）
输出：
  data/build/words.json     清洗后的词条（按等级、按套切好）
  data/build/rejected.csv   被丢弃的词条及原因（供人工抽查）

清洗规则（全部可追溯）：
  1. 释义为空 -> 丢弃
  2. 释义里出现 3 个及以上连续英文字母 -> 丢弃（多是词性缩写或拆分残留）
  3. 单词含非 ASCII 字符 -> 丢弃
  4. 单词带括号/斜杠等符号 -> 只保留纯字母和空格的词
  5. 同一等级内重复（忽略大小写）-> 只保留第一次出现
  6. 词组（含空格）标记出来，拼写/跟读模块不使用
"""

import csv
import json
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "sources" / "kylebing"
OUT = ROOT / "data" / "build"

# 年级 -> 等级
GRADE_LEVEL = {
    "人教小学三年级": "L1",
    "人教小学四年级": "L1",
    "人教小学五年级": "L2",
    "人教小学六年级": "L2",
    "人教初中七年级": "L3",
    "人教初中八年级": "L3",
}

SET_SIZE = 15
LATIN_RUN = re.compile(r"[A-Za-z]{3,}")
CLEAN_WORD = re.compile(r"^[A-Za-z][A-Za-z' -]*$")
TRAILING_PUNCT = re.compile(r"[!?.,;:]+$")
PAREN_BLOCK = re.compile(r"[（(][^）)]*[）)]")


def clean_markup(text: str) -> str:
    """去掉括号里夹的英文注释，再判断是否还含英文。"""
    return PAREN_BLOCK.sub("", text)


def load():
    items = []
    for path in sorted(SRC.glob("*.jsonl")):
        grade = path.stem
        level = GRADE_LEVEL.get(grade)
        if level is None:
            continue
        for line in path.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            items.append((grade, level, row))
    return items


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    raw = load()
    print(f"原始词条：{len(raw)}")

    rejected = []
    kept: dict[str, OrderedDict] = {"L1": OrderedDict(), "L2": OrderedDict(), "L3": OrderedDict()}

    for grade, level, row in raw:
        word = TRAILING_PUNCT.sub("", (row.get("word") or "").strip())
        translations = row.get("translations") or []
        meaning = "；".join(
            t.get("translation", "").strip() for t in translations if t.get("translation")
        ).strip()

        def drop(reason: str):
            rejected.append({"grade": grade, "level": level, "word": word, "meaning": meaning, "reason": reason})

        if not word:
            drop("单词为空")
            continue
        if not meaning:
            drop("释义为空")
            continue
        if LATIN_RUN.search(clean_markup(meaning)):
            drop("释义里含英文（多为词性缩写或拆分残留）")
            continue
        if not word.isascii():
            drop("单词含非英文字符")
            continue
        if not CLEAN_WORD.match(word):
            drop("单词含特殊符号")
            continue

        key = word.lower()
        bucket = kept[level]
        if key in bucket:
            drop(f"同等级内重复（已收录自 {bucket[key]['grade']}）")
            continue

        bucket[key] = {
            "level": level,
            "grade": grade,
            "word": word,
            "word_lower": key,
            "meaning": meaning,
            "is_phrase": " " in word,
        }

    summary = []
    sets_out = {}
    for level, bucket in kept.items():
        words = list(bucket.values())
        single = [w for w in words if not w["is_phrase"]]
        phrases = [w for w in words if w["is_phrase"]]

        # 拼写/跟读只用单词；认识题两种都能用
        sets_for_spelling = [single[i : i + SET_SIZE] for i in range(0, len(single), SET_SIZE)]
        sets_for_reading = [words[i : i + SET_SIZE] for i in range(0, len(words), SET_SIZE)]

        sets_out[level] = {
            "words": words,
            "sets_recognition": len(sets_for_reading),
            "sets_spelling": len(sets_for_spelling),
            "single_words": len(single),
            "phrases": len(phrases),
        }
        summary.append((level, len(words), len(single), len(phrases), len(sets_for_reading), len(sets_for_spelling)))

        # 只保留完整的套（不足 15 词的尾套丢弃）
        sets_out[level]["sets_recognition"] = len(sets_for_reading) - (1 if len(words) % SET_SIZE else 0)
        sets_out[level]["sets_spelling"] = len(sets_for_spelling) - (1 if len(single) % SET_SIZE else 0)

    (OUT / "words.json").write_text(
        json.dumps(sets_out, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    with (OUT / "rejected.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["grade", "level", "word", "meaning", "reason"])
        writer.writeheader()
        writer.writerows(rejected)

    print(f"\n保留 {sum(len(b) for b in kept.values())} 条，丢弃 {len(rejected)} 条")
    print(f"{'等级':<4}{'词条':>6}{'单词':>6}{'词组':>6}{'认识套数':>10}{'拼写套数':>10}")
    for level, total, single, phrase, rec, spl in summary:
        print(f"{level:<4}{total:>6}{single:>6}{phrase:>6}{rec:>10}{spl:>10}")
    print(f"\n输出：{OUT / 'words.json'}")
    print(f"丢弃清单：{OUT / 'rejected.csv'}")


if __name__ == "__main__":
    main()
