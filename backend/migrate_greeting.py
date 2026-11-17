"""强制迁移：把看图猜词 138 词从「基础问候词」移出，并重建其 set_no>=2 的套。

会删除：基础问候词 set_no>=2 的题、以及这些题相关的 Attempt / QuestionFlower /
WrongQuestion / SetProgress（用户已确认可删）。set1(GREETINGS) 不动。
"""
import json

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

import seed_words as sw
from app.database import SessionLocal
from app.models import Attempt, KnowledgePoint, Progress, Question, QuestionFlower, SetProgress, WrongQuestion

MANIFEST = sw.PICQUIZ_MANIFEST


def main() -> None:
    pq = {it["word"].lower() for it in json.loads(MANIFEST.read_text(encoding="utf-8"))}
    data = json.loads(sw.WORDS.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        kp = db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.level == "L1", KnowledgePoint.sort_order == 2
            )
        ).scalar_one()
        print("KP:", kp.name)

        old_ids = db.execute(
            select(Question.id).where(
                Question.knowledge_point_id == kp.id, Question.set_no >= 2
            )
        ).scalars().all()
        print("待删除旧题:", len(old_ids))
        if old_ids:
            db.execute(update(Progress).where(Progress.last_question_id.in_(old_ids)).values(last_question_id=None))
            db.execute(delete(Attempt).where(Attempt.question_id.in_(old_ids)))
            db.execute(delete(QuestionFlower).where(QuestionFlower.question_id.in_(old_ids)))
            db.execute(delete(WrongQuestion).where(WrongQuestion.question_id.in_(old_ids)))
            db.execute(delete(Question).where(Question.id.in_(old_ids)))
        db.execute(
            delete(SetProgress).where(
                SetProgress.knowledge_point_id == kp.id, SetProgress.set_no >= 2
            )
        )
        db.commit()

        existing_stems = set(
            db.execute(
                select(Question.stem).where(Question.knowledge_point_id == kp.id)
            ).scalars()
        )
        cand = sw.pick_candidates(data["L1"]["words"], "word", existing_stems)
        cand = [c for c in cand if c["word"].lower() not in pq]
        rows = sw.build_rows(kp.id, cand, "word", 1)
        if rows:
            db.execute(
                pg_insert(Question).values(rows).on_conflict_do_nothing(
                    index_elements=["knowledge_point_id", "stem"]
                )
            )
            db.commit()

        total = db.execute(
            select(func.count()).select_from(Question).where(
                Question.knowledge_point_id == kp.id
            )
        ).scalar_one()
        maxset = db.execute(
            select(func.max(Question.set_no)).where(
                Question.knowledge_point_id == kp.id
            )
        ).scalar_one()
        # 校验：还有没有残留的看图猜词词
        left = 0
        for q in db.execute(select(Question).where(Question.knowledge_point_id == kp.id)).scalars():
            opts = q.options or {}
            ans = opts.get(q.answer) if isinstance(opts, dict) else None
            if ans and ans.lower() in pq:
                left += 1
        print(f"重建后：{total} 题 / {maxset} 套；残留可画词 {left} 个；候选词 {len(cand)}")


if __name__ == "__main__":
    main()
