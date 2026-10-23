from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import KnowledgePoint, Progress, Question, User, WrongQuestion
from ..schemas import WrongItem, WrongListResponse
from ..services.attempts import MASTERY_STREAK

router = APIRouter(prefix="/api", tags=["wrong-questions"])


@router.get("/wrong-questions", response_model=WrongListResponse)
def list_wrong_questions(
    scope: Literal["current", "all"] = "current",
    include_mastered: bool = False,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    progress = db.get(Progress, user.id)
    current_kp_id = progress.current_knowledge_point_id if progress else None

    stmt = (
        select(WrongQuestion, Question, KnowledgePoint)
        .join(Question, Question.id == WrongQuestion.question_id)
        .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
        .where(WrongQuestion.user_id == user.id)
    )

    if scope == "current" and current_kp_id is not None:
        stmt = stmt.where(Question.knowledge_point_id == current_kp_id)

    if not include_mastered:
        stmt = stmt.where(WrongQuestion.consecutive_correct < MASTERY_STREAK)

    rows = db.execute(stmt).all()

    def sort_key(row):
        wrong, question, _kp = row
        is_current = 1 if current_kp_id and question.knowledge_point_id == current_kp_id else 0
        return (-is_current, -wrong.error_count)

    rows = sorted(rows, key=sort_key)

    items = [
        WrongItem(
            question_id=str(question.id),
            stem=question.stem,
            knowledge_point_name=kp.name,
            error_count=wrong.error_count,
            is_mastered=wrong.consecutive_correct >= MASTERY_STREAK,
        )
        for wrong, question, kp in rows
    ]
    return WrongListResponse(items=items)
