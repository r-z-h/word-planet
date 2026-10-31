"""把「多义拼接」的题干清洗成主义项（只取第一个义项）。

背景：题库题干来自 words.json 的 meaning，早期用了 kylebing 的多义串
（如「男孩, 儿子, 孩子气的人」），导致题干很长、歧义。这里做两件事：

1. 清洗 data/build/words.json 的 meaning（保留原文件备份）
2. 同步更新已有 Question 的 stem / explanation（不动选项与答案）

用法：
    python clean_stems.py            # 只预览（不写库、不写文件）
    python clean_stems.py --apply    # 真正执行
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Question  # noqa: E402

SEPS = set('，,')  # 只处理「多义拼接」的逗号；顿号/分号多为正常并列，保留
OPEN = set('（(【[')
CLOSE = set('）)】]')


def first_sense(text: str) -> str:
    """按分隔符取第一个义项；括号内的分隔符不算。"""
    if not text:
        return text
    depth = 0
    for i, ch in enumerate(text):
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth = max(0, depth - 1)
        elif ch in SEPS and depth == 0:
            head = text[:i].strip()
            if head:
                return head
    return text.strip()


def all_senses(text: str):
    """按顶层逗号切出全部义项（括号内逗号不算）。"""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth = max(0, depth - 1)
        elif ch in SEPS and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
    out.append(text[start:].strip())
    return [s for s in out if s]


def split_stem(stem: str):
    """从 “xxx”用英语怎么说？ 里取出 xxx。"""
    if '“' in stem and '”' in stem:
        a = stem.index('“')
        b = stem.index('”', a + 1)
        return stem[a + 1 : b], stem[: a + 1], stem[b:]
    return None, None, None


def walk_meaning(obj, changes):
    """递归清理 words.json 里所有含 meaning 的条目。"""
    if isinstance(obj, dict):
        if isinstance(obj.get('meaning'), str):
            old = obj['meaning']
            new = first_sense(old)
            if new != old:
                obj['meaning'] = new
                changes.append((obj.get('word') or obj.get('w') or '?', old, new))
        for v in obj.values():
            walk_meaning(v, changes)
    elif isinstance(obj, list):
        for v in obj:
            walk_meaning(v, changes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    words_path = root / 'data' / 'build' / 'words.json'

    # ---- 1. words.json ----
    data = json.loads(words_path.read_text(encoding='utf-8'))
    wchanges = []
    walk_meaning(data, wchanges)

    # ---- 2. 数据库题干 ----
    db_changes = []  # (id, kp_id, qtype, old, new)
    with SessionLocal() as db:
        questions = db.execute(select(Question)).scalars().all()
        for q in questions:
            inner, pre, post = split_stem(q.stem or '')
            if not inner:
                continue
            new_inner = first_sense(inner)
            if new_inner and new_inner != inner:
                db_changes.append((q.id, q.knowledge_point_id, q.question_type, inner, new_inner, q.stem))

    print(f'words.json 待改义项：{len(wchanges)}')
    print(f'数据库待改题干：{len(db_changes)} / 共 {len(questions)} 题')
    for w, old, new in wchanges[:5]:
        print(f'  [words] {w}: {old!r} -> {new!r}')
    for _id, _kp, qtype, old, new, _st in db_changes[:5]:
        print(f'  [db] {qtype}: {old!r} -> {new!r}')

    if not args.apply:
        print('\n（预览模式，未写入。加 --apply 执行）')
        return

    # 备份 words.json
    bak = words_path.with_suffix('.json.bak')
    if not bak.exists():
        shutil.copy2(words_path, bak)
        print('已备份 ->', bak.name)
    words_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    applied = skipped = 0
    with SessionLocal() as db:
        # 每个知识点已占用的题干（避免清洗后重名触发唯一约束）
        used: dict = {}
        for qid, kp_id, _t, _o, _n, stem in db_changes:
            used.setdefault(str(kp_id), set())
        allst = db.execute(select(Question.knowledge_point_id, Question.stem)).all()
        for kp_id, stem in allst:
            used.setdefault(str(kp_id), set()).add(stem)

        for qid, kp_id, _t, old, new, old_stem in db_changes:
            bucket = used[str(kp_id)]
            target = old_stem.replace(f'“{old}”', f'“{new}”')
            if target in bucket:
                # 主义项与同星球别的题重名：从原多义里另挑一个不冲突的义项
                alt = None
                for seg in all_senses(old):
                    cand = old_stem.replace(f'“{old}”', f'“{seg}”')
                    if seg != old and cand not in bucket:
                        alt = seg
                        break
                if alt is None:
                    skipped += 1
                    continue
                new = alt
                target = old_stem.replace(f'“{old}”', f'“{new}”')
            q = db.get(Question, qid)
            if q is None:
                continue
            bucket.discard(q.stem)
            q.stem = target
            if q.explanation:
                q.explanation = q.explanation.replace(f'“{old}”', f'“{new}”')
            bucket.add(target)
            applied += 1
        db.commit()

    print(f'完成：更新 {applied} 条；因清洗后重名跳过 {skipped} 条（保留原题干）。')


if __name__ == '__main__':
    main()
