from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Attempt, DailyTask, KnowledgePoint, Progress, Question, User, WrongQuestion
from ..schemas import DailyAttempt, ReportResponse, ReportWrongItem
from ..services.attempts import MASTERY_STREAK, local_date_of, local_today

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report", response_model=ReportResponse)
def report(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    progress = db.get(Progress, user.id)
    completed = list(dict.fromkeys(progress.completed_knowledge_points or [])) if progress else []

    total_kp = 0
    if user.level:
        total_kp = db.execute(
            select(func.count()).select_from(KnowledgePoint).where(
                KnowledgePoint.level == user.level
            )
        ).scalar_one()

    today = local_today(db)
    since = today - timedelta(days=6)

    completed_days = db.execute(
        select(func.count())
        .select_from(DailyTask)
        .where(
            DailyTask.user_id == user.id,
            DailyTask.is_completed.is_(True),
            DailyTask.task_date >= since,
            DailyTask.task_date <= today,
        )
    ).scalar_one()

    day_col = local_date_of(Attempt.created_at).label("d")
    attempt_rows = db.execute(
        select(day_col, func.count())
        .where(
            Attempt.user_id == user.id,
            local_date_of(Attempt.created_at) >= since,
            local_date_of(Attempt.created_at) <= today,
        )
        .group_by(day_col)
        .order_by(day_col)
    ).all()
    counts = {row[0]: row[1] for row in attempt_rows}

    daily_attempts = [
        DailyAttempt(date=since + timedelta(days=i), count=counts.get(since + timedelta(days=i), 0))
        for i in range(7)
    ]

    wrong_rows = db.execute(
        select(WrongQuestion, Question)
        .join(Question, Question.id == WrongQuestion.question_id)
        .where(WrongQuestion.user_id == user.id)
        .order_by(WrongQuestion.error_count.desc())
        .limit(20)
    ).all()

    return ReportResponse(
        level=user.level,
        completed_knowledge_points=len(completed),
        total_knowledge_points=total_kp,
        last_7_days_completed=completed_days,
        daily_attempts=daily_attempts,
        wrong_questions=[
            ReportWrongItem(
                stem=question.stem,
                error_count=wrong.error_count,
                is_mastered=wrong.consecutive_correct >= MASTERY_STREAK,
            )
            for wrong, question in wrong_rows
        ],
    )
