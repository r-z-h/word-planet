from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_tested
from ..models import Attempt, DailyTask, KnowledgePoint, Progress, Question, Streak, User
from ..schemas import ProgressResponse, StreakResponse, TodayTaskOut
from ..services.attempts import local_date_of, local_today

router = APIRouter(prefix="/api", tags=["progress"])


@router.get("/progress", response_model=ProgressResponse)
def get_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = db.get(Progress, user.id)
    completed = []
    current_kp = None
    if progress is not None:
        completed = list(dict.fromkeys(progress.completed_knowledge_points or []))
        if progress.current_knowledge_point_id:
            current_kp = db.get(KnowledgePoint, progress.current_knowledge_point_id)

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

    target_count = 0
    kp_total = 0
    kp_done = 0
    if current_kp is not None:
        qids_stmt = select(Question.id).where(Question.knowledge_point_id == current_kp.id)
        kp_total = db.execute(
            select(func.count()).select_from(Question).where(
                Question.knowledge_point_id == current_kp.id
            )
        ).scalar_one()

        # 做过的题（对错都算，练习不算），与 6.3 的完成判定一致
        kp_done = db.execute(
            select(func.count(func.distinct(Attempt.question_id))).where(
                Attempt.user_id == user.id,
                Attempt.question_id.in_(qids_stmt),
                Attempt.question_type != "practice",
            )
        ).scalar_one()

        target_count = max(kp_total - kp_done, 0)

    return ProgressResponse(
        level=user.level,
        current_knowledge_point=(
            {
                "id": str(current_kp.id),
                "level": current_kp.level,
                "name": current_kp.name,
                "question_type": current_kp.question_type,
            }
            if current_kp
            else None
        ),
        completed_knowledge_points=completed,
        today_task=TodayTaskOut(
            is_completed=bool(task.is_completed) if task else False,
            correct_count=correct_count,
            target_count=target_count,
        ),
        kp_total=kp_total,
        kp_done=kp_done,
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
