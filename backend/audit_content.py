"""题库内容审计：只做机器能判定的硬性检查，不做语义判断。

检查项：
1. 每题解析非空
2. 选择题：答案 key 合法、对应选项文本非空、四个选项互不相同
3. 字母题：题干里的序数与选项文本一致（第 N 个 = chr(64+N)）
4. 听力题：正确词必须出现在句子里；干扰项必须不出现（按整词匹配）
5. 拼写题：答案只能是纯小写字母
6. 同一知识点内题干不重复
"""

import re
import sys
import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import KnowledgePoint, Question

problems: list[str] = []


def add(q: Question, msg: str) -> None:
    problems.append(f"[{q.question_type}] {q.stem[:40]} -> {msg}")


def word_in(needle: str, haystack: str) -> bool:
    return re.search(rf"\b{re.escape(needle)}\b", haystack, re.IGNORECASE) is not None


def main() -> None:
    with SessionLocal() as db:
        rows = db.execute(select(Question).order_by(Question.question_type, Question.stem)).scalars().all()
        kps = {k.id: k for k in db.execute(select(KnowledgePoint)).scalars().all()}

        print(f"题目总数：{len(rows)}")

        seen_stems: dict[tuple, str] = {}

        for q in rows:
            kp = kps.get(q.knowledge_point_id)

            if not q.explanation or not q.explanation.strip():
                add(q, "缺少解析")

            key = (q.knowledge_point_id, q.stem)
            if key in seen_stems:
                add(q, "题干重复")
            seen_stems[key] = str(q.id)

            if q.question_type in ("letter", "word", "listening"):
                opts = q.options or {}
                if sorted(opts.keys()) != ["A", "B", "C", "D"]:
                    add(q, f"选项 key 异常：{sorted(opts.keys())}")
                    continue
                if q.answer not in opts:
                    add(q, f"答案 {q.answer} 不在选项里")
                    continue
                texts = [str(v).strip() for v in opts.values()]
                if any(not t for t in texts):
                    add(q, "存在空选项")
                if len(set(texts)) != 4:
                    add(q, f"选项重复：{texts}")

                if q.question_type == "letter":
                    m = re.search(r"第\s*(\d+)\s*个", q.stem)
                    if not m:
                        add(q, "题干里找不到序数")
                    else:
                        expect = chr(64 + int(m.group(1)))
                        got = str(opts[q.answer]).strip()
                        if got != expect:
                            add(q, f"序数与答案不符：期望 {expect}，实际 {got}")

                if q.question_type == "listening":
                    correct_text = str(opts[q.answer]).strip()
                    if not word_in(correct_text, q.stem):
                        add(q, f"正确词「{correct_text}」不在句子里")
                    for k, v in opts.items():
                        if k == q.answer:
                            continue
                        if word_in(str(v), q.stem):
                            add(q, f"干扰项「{v}」也出现在句子里")
                        # 更严格：连"作为词的一部分出现"也算隐患
                        # 例如句子里有 brothers、干扰项是 brother，听感上分不出来
                        elif str(v).lower() in q.stem.lower():
                            add(q, f"干扰项「{v}」是句子里某个词的一部分，容易混淆")

            if q.question_type == "spelling":
                if q.options:
                    add(q, "拼写题不应有选项")
                # 判题时大小写不敏感，专有名词（Alaska）允许首字母大写
                if not re.fullmatch(r"[A-Za-z]+", str(q.answer)):
                    add(q, f"答案不是纯英文字母：{q.answer}")

            if q.question_type == "pronunciation":
                if not re.fullmatch(r"[A-Za-z]+", str(q.answer)):
                    add(q, f"跟读答案异常：{q.answer}")

        # 题量与题型一致性：按「套」检查，每套必须 15 题
        for kp_id, kp in kps.items():
            qs = [x for x in rows if x.knowledge_point_id == kp_id]
            types = {x.question_type for x in qs}
            if types != {kp.question_type}:
                problems.append(f"知识点「{kp.name}」题型不一致：{types}")
            per_set: dict[int, int] = {}
            for q in qs:
                per_set[q.set_no] = per_set.get(q.set_no, 0) + 1
            for set_no, count in sorted(per_set.items()):
                if count != 15:
                    problems.append(
                        f"「{kp.name}」第 {set_no} 套只有 {count} 题（应为 15）"
                    )

    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    print("\n机器可判定的检查全部通过。")


if __name__ == "__main__":
    main()
