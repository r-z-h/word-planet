from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_tested
from ..models import Attempt, DailyTask, KnowledgePoint, Progress, Question, Streak, User
from ..schemas import ProgressResponse, StreakResponse, TodayTaskOut
from ..services.attempts import local_date_of, local_today
from ..services.lesson import (
    completed_set_numbers,
    current_set_no,
    kp_set_numbers,
    resolve_current_kp,
)

router = APIRouter(prefix="/api", tags=["progress"])


def _kp_out(kp: KnowledgePoint | None) -> dict | None:
    if kp is None:
        return None
    return {
        "id": str(kp.id),
        "level": kp.level,
        "name": kp.name,
        "question_type": kp.question_type,
    }


@router.get("/progress", response_model=ProgressResponse)
def get_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = db.get(Progress, user.id)
    completed = list(dict.fromkeys(progress.completed_knowledge_points or [])) if progress else []

    current_kp = resolve_current_kp(db, user) if user.has_tested else None

    today = local_today(db)
    task = db.execute(
        select(DailyTask).where(DailyTask.user_id == user.id, DailyTask.task_date == today)
    ).scalar_one_or_none()

    correct_count = db.execute(
        select(func.count())
        .select_from(Attempt)
        .where(
            Attempt.user_id == user.id,
            Attempt.is_correct.is_(True),
            local_date_of(Attempt.created_at) == today,
        )
    ).scalar_one()

    set_no = None
    set_total = 0
    set_done = 0
    done_sets = 0
    total_sets = 0

    if current_kp is not None:
        total_sets = len(kp_set_numbers(db, current_kp.id))
        done_sets = len(completed_set_numbers(db, user.id, current_kp.id))
        set_no = current_set_no(db, user.id, current_kp.id)

        if set_no is not None:
            qids = select(Question.id).where(
                Question.knowledge_point_id == current_kp.id, Question.set_no == set_no
            )
            set_total = db.execute(
                select(func.count())
                .select_from(Question)
                .where(
                    Question.knowledge_point_id == current_kp.id,
                    Question.set_no == set_no,
                )
            ).scalar_one()
            set_done = db.execute(
                select(func.count(func.distinct(Attempt.question_id))).where(
                    Attempt.user_id == user.id,
                    Attempt.question_id.in_(qids),
                    Attempt.question_type != "practice",
                )
            ).scalar_one()

    target_count = max(set_total - set_done, 0)

    return ProgressResponse(
        level=user.level,
        max_level=user.max_level or user.level,
        current_knowledge_point=_kp_out(current_kp),
        completed_knowledge_points=completed,
        today_task=TodayTaskOut(
            is_completed=bool(task.is_completed) if task else False,
            correct_count=correct_count,
            target_count=target_count,
        ),
        kp_total=set_total,
        kp_done=set_done,
        set_no=set_no,
        completed_sets=done_sets,
        total_sets=total_sets,
    )


@router.get("/streak", response_model=StreakResponse)
def get_streak(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    streak = db.get(Streak, user.id)
    if streak is None:
        return StreakResponse(current_streak=0, longest_streak=0, last_study_date=None)
    return StreakResponse(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_study_date=streak.last_study_date,
    )
