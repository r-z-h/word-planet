"""把词表 + ECDICT 释义写入 words 表。"""

import json
from pathlib import Path

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import Word

ROOT = Path(__file__).resolve().parents[1]
WORDS = ROOT / "data" / "build" / "words.json"
SENSES = ROOT / "data" / "build" / "word_senses.json"

GRADE_ORDER = {
    "人教小学三年级": 10,
    "人教小学四年级": 20,
    "人教小学五年级": 30,
    "人教小学六年级": 40,
    "人教初中七年级": 50,
    "人教初中八年级": 60,
}


def main() -> None:
    words = json.loads(WORDS.read_text(encoding="utf-8"))
    senses = json.loads(SENSES.read_text(encoding="utf-8"))

    rows = []
    seen = set()
    for level in ("L1", "L2", "L3"):
        for idx, item in enumerate(words[level]["words"]):
            key = item["word"].lower()
            info = senses.get(key)
            if info:
                sense_list = info["senses"]
                phonetic = info.get("phonetic") or None
                definition = info.get("definition_en")
            else:
                # 词典没收录（多为词组）：回退到教材释义
                sense_list = [s.strip() for s in item["meaning"].split("；") if s.strip()]
                phonetic = None
                definition = None

            if key in seen:
                continue
            seen.add(key)
            base = GRADE_ORDER.get(item["grade"], 99)
            rows.append(
                {
                    "word": key,
                    "display": item["word"],
                    "level": level,
                    "grade": item["grade"],
                    "order_index": base * 10000 + idx,
                    "phonetic": phonetic,
                    "senses": sense_list,
                    "definition_en": definition,
                    "is_phrase": bool(item.get("is_phrase")),
                }
            )

    with SessionLocal() as db:
        db.execute(delete(Word))
        db.commit()
        db.bulk_insert_mappings(Word, rows)
        db.commit()

        total = db.execute(select(Word)).scalars().all()
        print(f"写入 {len(rows)} 个词")
        for level in ("L1", "L2", "L3"):
            n = len([w for w in total if w.level == level])
            multi = len([w for w in total if w.level == level and len(w.senses) > 1])
            print(f"  {level}: {n} 词，多义项 {multi}")
        print("示例：", [(w.display, w.senses[:2]) for w in total[:2]])


if __name__ == "__main__":
    main()
