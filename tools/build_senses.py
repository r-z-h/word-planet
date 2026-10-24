"""从 ECDICT 抽取本项目用到的单词的完整释义。

输入：data/sources/ecdict-repo/ecdict.csv（skywind3000/ECDICT，MIT）
      data/build/words.json（我们实际用到的词）
输出：data/build/word_senses.json
      { "word": {"phonetic": "...", "pos": "...", "senses": ["...", "..."]} }
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ECDICT = ROOT / "data" / "sources" / "ecdict-repo" / "ecdict.csv"
WORDS = ROOT / "data" / "build" / "words.json"
OUT = ROOT / "data" / "build" / "word_senses.json"


def main() -> None:
    words = json.loads(WORDS.read_text(encoding="utf-8"))
    wanted = {}
    for level in ("L1", "L2", "L3"):
        for item in words[level]["words"]:
            wanted.setdefault(item["word"].lower(), item)

    print(f"需要释义的词：{len(wanted)}")

    found = {}
    with ECDICT.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("word") or "").strip().lower()
            if key not in wanted or key in found:
                continue
            translation = (row.get("translation") or "").strip()
            if not translation:
                continue
            senses = [s.strip() for s in translation.split("\\n") if s.strip()]
            found[key] = {
                "word": wanted[key]["word"],
                "level": wanted[key]["level"],
                "phonetic": (row.get("phonetic") or "").strip(),
                "pos": (row.get("pos") or "").strip(),
                "senses": senses,
                "definition_en": (row.get("definition") or "").strip() or None,
            }

    OUT.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")

    missing = [w for w in wanted if w not in found]
    multi = sum(1 for v in found.values() if len(v["senses"]) > 1)
    print(f"命中 {len(found)} / {len(wanted)}，其中多义项 {multi} 个")
    print(f"未命中 {len(missing)} 个，示例：{missing[:10]}")
    print(f"输出：{OUT}")


if __name__ == "__main__":
    main()
