"""把词表 + ECDICT 释义写入 words 表。

课本义来源：data/sources/pep-words（人教版词表），按学段取
  L1/L2 -> primary_school.json，L3 -> middle_school.json，本学段没有则回退另一份。

三道工序：
  1. 机械清洗：去尾部标点、去相邻重复（动物园动物园 -> 动物园）、分隔符统一为「；」。
  2. ECDICT 侧：删带领域标签的义项；每条词性行按逗号拆开、逐项过滤生僻/俚语、
     与课本义重复的丢弃；每行最多留 2 项、全词最多留 3 行。
  3. 人工清洗：data/sense_cleanup.json 按等级分桶，命中的词整组覆盖（最终义项）。

用法：
  python import_dictionary.py               # 写库
  python import_dictionary.py --preview p   # 只生成预览 JSON，不写库
"""

import argparse
import json
import re
from pathlib import Path

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Word

ROOT = Path(__file__).resolve().parents[1]
WORDS = ROOT / "data" / "build" / "words.json"
SENSES = ROOT / "data" / "build" / "word_senses.json"
CLEANUP = ROOT / "data" / "sense_cleanup.json"
PEP_PRIMARY = ROOT / "data" / "sources" / "pep-words" / "primary_school.json"
PEP_MIDDLE = ROOT / "data" / "sources" / "pep-words" / "middle_school.json"

DOMAIN_TAG = re.compile(r"\[[^\]]+\]")  # [医][计][经] 等专业标签
POS_PREFIX = re.compile(r"^(n|v|vt|vi|a|adj|ad|adv|prep|pron|conj|num|art|int|interj|aux|pl)\.\s*")
POS_ANYWHERE = re.compile(r"(?<![A-Za-z])(n|v|vt|vi|a|adj|ad|adv|prep|pron|conj|num|art|int|interj|aux|pl)\.\s*")
ITEM_SPLIT = re.compile(r"[,，]")
# 词表自带的语法注记，如「儿童 \(child 的复数）」「（过去式bought[bɔ:t]）买」
LATIN_NOTE = re.compile(r"[（(][^（）()]*[A-Za-z][^（）()]*[）)]")
LATIN_BRACKET = re.compile(r"\[[^\]]*[A-Za-z][^\]]*\]")
CJK = r"\u4e00-\u9fff"

# 这些词一出现就说明这条释义对孩子没意义：技术/领域词、俚语脏话、语法标注
JUNK_MARKERS = (
    "计算机",
    "程序",
    "文件",
    "数据",
    "网络",
    "电报",
    "雷达",
    "化学",
    "物理",
    "军事",
    "军火",
    "股票",
    "证券",
    "会计",
    "法律",
    "诉讼",
    "解剖",
    "语法",
    "恶妇",
    "坏蛋",
    "妓",
    "婊",
    "混蛋",
    "该死",
    "见鬼",
    "色情",
    "色鬼",
    "下流",
    "骂人",
    "骗子",
    "特务",
    "走狗",
    "酒鬼",
    "荡妇",
    "的过去式",
    "的过去分词",
    "的复数",
    "的现在分词",
    "的ing形式",
)

MAX_ITEMS_PER_LINE = 2
MAX_DICT_LINES = 3

GRADE_ORDER = {
    "人教小学三年级": 10,
    "人教小学四年级": 20,
    "人教小学五年级": 30,
    "人教小学六年级": 40,
    "人教初中七年级": 50,
    "人教初中八年级": 60,
}


CJK = "\u4e00-\u9fff"


def clean_gloss(text: str) -> str:
    """机械清洗：去注记、去尾部标点、去相邻重复、统一分隔符。不做语义判断。"""
    s = (text or "").replace("\\(", "(").replace("\\)", ")")
    s = LATIN_NOTE.sub("", s)
    s = LATIN_BRACKET.sub("", s)
    s = DOMAIN_TAG.sub("", s)
    parts = []
    for part in re.split(r"[;；]", s):
        part = POS_ANYWHERE.sub("", part)
        part = re.sub(rf"\s+(?=[{CJK}])|(?<=[{CJK}])\s+", "", part)
        part = re.sub(r"\s+", " ", part)
        part = part.strip(" \t.,:。；，、")
        half = len(part) // 2
        if len(part) >= 4 and len(part) % 2 == 0 and part[:half] == part[half:]:
            part = part[:half]
        if part:
            parts.append(part)
    s = "；".join(parts)
    s = re.sub(r"；{2,}", "；", s)
    return s.strip("； ")


def load_pep() -> tuple[dict[str, str], dict[str, str]]:
    """返回（小学词表, 初中词表），key 为小写单词。"""

    def load(path: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        if not path.exists():
            return out
        for item in json.loads(path.read_text(encoding="utf-8")):
            word = str(item.get("word", "")).strip().lower()
            gloss = clean_gloss(str(item.get("meaning", "")))
            if word and gloss:
                out.setdefault(word, gloss)
        return out

    return load(PEP_PRIMARY), load(PEP_MIDDLE)


def textbook_glosses(
    word: str, level: str, fallback: list[str], pep: tuple[dict[str, str], dict[str, str]]
) -> list[str]:
    primary, middle = pep
    first, second = (primary, middle) if level != "L3" else (middle, primary)
    gloss = first.get(word) or second.get(word)
    if gloss:
        return [gloss]
    return fallback


def is_junk_item(item: str) -> bool:
    return any(marker in item for marker in JUNK_MARKERS)


def covered_by(text: str, glosses: list[str]) -> bool:
    return any(text == g or text in g or g in text for g in glosses)


def dict_senses(raw_senses: list[str], textbook: list[str]) -> list[dict]:
    """ECDICT 原始释义 -> 清洗后的 dict 义项。"""
    out: list[dict] = []
    seen: set[str] = set()
    for raw in raw_senses:
        if DOMAIN_TAG.search(raw):
            continue
        match = POS_PREFIX.match(raw)
        pos = match.group(0).rstrip() if match else ""
        body = POS_PREFIX.sub("", raw).strip()
        if not body or is_junk_item(body):
            continue
        items = [x.strip() for x in ITEM_SPLIT.split(body) if x.strip()]
        items = [x for x in items if not is_junk_item(x)]
        items = [x for x in items if not covered_by(x, textbook)]
        items = items[:MAX_ITEMS_PER_LINE]
        if not items:
            continue
        text = f"{pos} {'，'.join(items)}".strip()
        if text in seen:
            continue
        seen.add(text)
        out.append({"text": text, "source": "dict"})
        if len(out) >= MAX_DICT_LINES:
            break
    return out


def build_senses(
    word: str,
    level: str,
    textbook: list[str],
    info: dict | None,
    pep: tuple[dict[str, str], dict[str, str]],
    cleanup: dict,
) -> list[dict]:
    curated = cleanup.get("levels", {}).get(level, {}).get(word)
    if curated:
        out = []
        for index, entry in enumerate(curated):
            if isinstance(entry, list):
                text = entry[0]
                source = entry[1] if len(entry) > 1 else None
            else:
                text, source = entry, None
            if not source:
                if index == 0:
                    # 人工清单的第一条就是课本义（也可能是纠正过的课本义）
                    source = "textbook"
                else:
                    source = "textbook" if text in textbook else "dict"
            out.append({"text": text, "source": source})
        return out

    senses = [{"text": text, "source": "textbook"} for text in textbook]
    if info:
        senses += dict_senses(info.get("senses") or [], textbook)
    if not senses:
        senses = [{"text": text, "source": "textbook"} for text in textbook]
    return senses


def build_rows(cleanup: dict) -> list[dict]:
    words = json.loads(WORDS.read_text(encoding="utf-8"))
    senses_index = json.loads(SENSES.read_text(encoding="utf-8"))
    pep = load_pep()

    rows = []
    seen = set()
    for level in ("L1", "L2", "L3"):
        for idx, item in enumerate(words[level]["words"]):
            key = item["word"].lower()
            if key in seen:
                continue
            seen.add(key)

            info = senses_index.get(key)
            fallback = [s.strip() for s in item["meaning"].split("；") if s.strip()]
            textbook = [clean_gloss(s) for s in textbook_glosses(key, level, fallback, pep)]
            textbook = [s for s in textbook if s]
            fix = cleanup.get("textbook_fixes", {}).get(level, {}).get(key)
            if fix:
                textbook = [fix]
            sense_list = build_senses(key, level, textbook, info, pep, cleanup)
            if not sense_list:
                sense_list = [{"text": s, "source": "textbook"} for s in fallback]

            base = GRADE_ORDER.get(item["grade"], 99)
            definition = (info or {}).get("definition_en")
            if definition:
                # ECDICT 里是字面量 \n，换行要还原成真换行
                definition = definition.replace("\\n", "\n").strip()
            rows.append(
                {
                    "word": key,
                    "display": item["word"],
                    "level": level,
                    "grade": item["grade"],
                    "order_index": base * 10000 + idx,
                    "phonetic": (info or {}).get("phonetic") or None,
                    "senses": sense_list,
                    "definition_en": definition,
                    "is_phrase": bool(item.get("is_phrase")),
                }
            )
    return rows


def load_cleanup() -> dict:
    if not CLEANUP.exists():
        return {"levels": {}, "textbook_fixes": {}}
    doc = json.loads(CLEANUP.read_text(encoding="utf-8"))
    # 词表里 China/English 这类是显示大小写，查表统一用小写
    doc["levels"] = {
        level: {word.lower(): senses for word, senses in bucket.items()}
        for level, bucket in doc.get("levels", {}).items()
    }
    doc["textbook_fixes"] = {
        level: {word.lower(): text for word, text in bucket.items()}
        for level, bucket in doc.get("textbook_fixes", {}).items()
    }
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", metavar="PATH", help="只写预览 JSON，不写库")
    args = parser.parse_args()

    cleanup = load_cleanup()
    rows = build_rows(cleanup)

    if args.preview:
        out = Path(args.preview)
        out.write_text(
            json.dumps(
                [
                    {
                        "level": r["level"],
                        "word": r["display"],
                        "senses": r["senses"],
                    }
                    for r in rows
                ],
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"预览已写入 {out}（{len(rows)} 词，未写库）")
        return

    with SessionLocal() as db:
        db.execute(delete(Word))
        db.commit()
        db.bulk_insert_mappings(Word, rows)
        db.commit()

        total = db.execute(select(Word)).scalars().all()
        print(f"写入 {len(rows)} 个词")
        for level in ("L1", "L2", "L3"):
            sub = [w for w in total if w.level == level]
            multi = len([w for w in sub if len(w.senses) > 1])
            counts = [len(w.senses) for w in sub]
            print(
                f"  {level}: {len(sub)} 词，多义项 {multi}，"
                f"平均 {sum(counts) / max(len(counts), 1):.2f} 条，最多 {max(counts) if counts else 0} 条"
            )
        sample = [w for w in total if w.word in ("boy", "red", "plane", "event")]
        print("示例：", [(w.display, [s["text"] for s in w.senses]) for w in sample])


if __name__ == "__main__":
    main()
