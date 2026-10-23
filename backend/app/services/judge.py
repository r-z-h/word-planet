from ..models import Question

CHOICE_TYPES = {"letter", "word", "listening"}


def normalize(question: Question, raw: str) -> str:
    text = (raw or "").strip()
    if question.question_type in CHOICE_TYPES:
        return text.upper()
    return text.lower()


def is_correct(question: Question, raw: str) -> bool:
    return normalize(question, raw) == normalize(question, str(question.answer))
