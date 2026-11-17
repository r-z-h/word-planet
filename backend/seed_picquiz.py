"""把 138 个看图猜词词建成「看图猜词」知识点题目（9 主题 = set_no 1..9）。

注意：此脚本会改数据库；暂未自动执行，等花/星/徽记兑换链打通后再运行。
运行：cd backend; .\\.venv\\Scripts\\python.exe seed_picquiz.py
"""
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint, Question

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "frontend" / "public" / "picquiz_imgs" / "manifest.json"
ORDER = ["people", "animals", "food", "body", "school", "places", "clothes", "objects", "weather"]
KEYS = "ABCD"


def main() -> None:
    data = json.load(open(MANIFEST, encoding="utf-8"))
    by_cat = defaultdict(list)
    for it in data:
        by_cat[it["cat"]].append(it)

    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint).where(KnowledgePoint.name == "看图猜词")
        ).scalar_one_or_none()
        if kp is None:
            kp = KnowledgePoint(
                level="L1", name="看图猜词", question_type="picquiz", sort_order=3,
                counts_for_gate=True, gate_mode="medals", gate_required=5,
                medal_name="眼力侠", medal_icon="/medals/eyeman.png", produces_flowers=False,
            )
            db.add(kp)
            db.flush()
        else:
            kp.question_type = "picquiz"
            kp.counts_for_gate = True
            kp.gate_mode = "medals"
            kp.gate_required = 5
            kp.medal_name = "眼力侠"
            kp.medal_icon = "/medals/eyeman.png"
            kp.produces_flowers = False

        # 字母表：不计解锁门槛
        alpha = db.execute(
            select(KnowledgePoint).where(KnowledgePoint.name == "字母表")
        ).scalar_one_or_none()
        if alpha is not None:
            alpha.counts_for_gate = False

        n = 0
        for set_no, cat in enumerate(ORDER, 1):
            items = by_cat.get(cat, [])
            words = [x["word"] for x in items]
            total = len(words)
            for idx, it in enumerate(items):
                word, cn = it["word"], it["cn"]
                wrongs = [words[(idx + k) % total] for k in (1, 2, 3)]
                pos = idx % 4
                opts = list(wrongs)
                opts.insert(pos, word)
                options = {KEYS[i]: opts[i] for i in range(4)}
                ans = KEYS[pos]
                q = db.execute(
                    select(Question).where(
                        Question.knowledge_point_id == kp.id, Question.stem == word
                    )
                ).scalar_one_or_none()
                if q is None:
                    db.add(
                        Question(
                            knowledge_point_id=kp.id, question_type="picquiz", stem=word,
                            options=options, answer=ans, explanation=f"{word} = {cn}",
                            set_no=set_no, difficulty=1,
                        )
                    )
                else:
                    q.question_type = "picquiz"
                    q.options = options
                    q.answer = ans
                    q.set_no = set_no
                    q.explanation = f"{word} = {cn}"
                n += 1
        db.commit()
        cnt = len(
            db.execute(
                select(Question).where(Question.knowledge_point_id == kp.id)
            ).scalars().all()
        )
        print(f"看图猜词题 {cnt} 道，本次处理 {n}")


if __name__ == "__main__":
    main()
