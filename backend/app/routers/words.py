"""词典页：按当前等级列出单词，带「已学 / 有错题」状态。

状态口径（已拍板）：
- 已学 = 该词对应的题目至少答对过一次（对错都算「做过」，但这里按答对算）。
- 有错题 = 该词对应的题目进过错题本（不论是否已掌握）。
单词与题目的对应关系：拼写/跟读题直接取 answer；
选择题取正确选项（answer 是选项 key）的文本。字母题不参与。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, KnowledgePoint, Question, User, Word, WrongQuestion
from ..schemas import WordItemOut, WordListResponse, WordSenseOut
from ..services.words import question_word

router = APIRouter(prefix="/api/words", tags=["dictionary"])

PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


def _question_word_index(db: Session, level: str) -> tuple[dict, dict]:
    """返回（题目 id -> 单词, 单词 -> 题目 id 集合）。"""
    rows = db.execute(
        select(Question)
        .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
        .where(KnowledgePoint.level == level)
    ).scalars()
    qid_to_word: dict = {}
    word_to_qids: dict = {}
    for question in rows:
        word = question_word(question)
        if not word:
            continue
        qid_to_word[question.id] = word
        word_to_qids.setdefault(word, set()).add(question.id)
    return qid_to_word, word_to_qids


@router.get("", response_model=WordListResponse)
def list_words(
    q: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    level = user.level or "L1"
    qid_to_word, _ = _question_word_index(db, level)

    learned = {
        qid_to_word[qid]
        for qid in db.execute(
            select(Attempt.question_id).where(
                Attempt.user_id == user.id, Attempt.is_correct.is_(True)
            )
        ).scalars()
        if qid in qid_to_word
    }
    has_wrong = {
        qid_to_word[qid]
        for qid in db.execute(
            select(WrongQuestion.question_id).where(WrongQuestion.user_id == user.id)
        ).scalars()
        if qid in qid_to_word
    }

    words = db.execute(select(Word).where(Word.level == level)).scalars().all()

    keyword = q.strip().lower()

    def matches(word: Word) -> bool:
        if not keyword:
            return True
        if keyword in word.word.lower() or keyword in word.display.lower():
            return True
        if word.phonetic and keyword in word.phonetic.lower():
            return True
        return any(keyword in str(sense.get("text", "")).lower() for sense in word.senses)

    rows = [word for word in words if matches(word)]
    rows.sort(key=lambda word: (word.word.lower() in learned, word.order_index))

    total = len(rows)
    page = rows[offset : offset + limit]

    items = [
        WordItemOut(
            id=str(word.id),
            word=word.display,
            phonetic=word.phonetic,
            level=word.level,
            grade=word.grade,
            is_phrase=word.is_phrase,
            senses=[WordSenseOut(**sense) for sense in word.senses],
            definition_en=word.definition_en if level == "L3" else None,
            learned=word.word.lower() in learned,
            has_wrong=word.word.lower() in has_wrong,
        )
        for word in page
    ]

    return WordListResponse(
        level=level,
        total=total,
        items=items,
        has_more=offset + len(page) < total,
    )
