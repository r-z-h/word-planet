"""题目 -> 单词 的公共映射。

选择题的 answer 是选项 key，正确选项的文本才是单词；拼写/跟读的 answer 就是单词。
字母题的选项是字母，不对应 words 表里的词，返回 None。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Question, Word


def question_word(question: Question) -> str | None:
    if question.question_type in ("spelling", "pronunciation"):
        return str(question.answer).strip().lower() or None
    if isinstance(question.options, dict):
        key = str(question.answer).strip()
        value = question.options.get(key.upper()) or question.options.get(key)
        if value:
            return str(value).strip().lower()
    return None


def answer_text(question: Question) -> str | None:
    """正确答案的展示文本：选择题取选项内容，其它取 answer。"""
    if isinstance(question.options, dict):
        key = str(question.answer).strip()
        value = question.options.get(key.upper()) or question.options.get(key)
        if value:
            return str(value)
    return str(question.answer)


def word_payload(db: Session, question: Question) -> dict | None:
    """答错时要展示的单词信息，查不到就返回 None（例如字母题）。"""
    key = question_word(question)
    if not key:
        return None
    word = db.execute(select(Word).where(Word.word == key)).scalar_one_or_none()
    if word is None:
        return None
    return {
        "word": word.display,
        "phonetic": word.phonetic,
        "senses": word.senses,
        "definition_en": word.definition_en if word.level == "L3" else None,
    }
