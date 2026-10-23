import json
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .models import Attempt, PushSubscription, User
from .services.attempts import local_date_of, local_today

logger = logging.getLogger("word_planet.scheduler")


def _users_to_remind():
    """当天没有任何答对记录、且有推送订阅的用户。"""
    with SessionLocal() as db:
        today = local_today(db)
        correct_today = (
            select(Attempt.user_id)
            .where(
                Attempt.is_correct.is_(True),
                local_date_of(Attempt.created_at) == today,
            )
            .scalar_subquery()
        )
        rows = db.execute(
            select(User.id, PushSubscription.subscription)
            .join(PushSubscription, PushSubscription.user_id == User.id)
            .where(User.id.notin_(correct_today))
        ).all()
        return list(rows)


def send_daily_reminders() -> None:
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush 未安装，跳过推送")
        return

    if not settings.vapid_private_key:
        logger.warning("VAPID_PRIVATE_KEY 为空，跳过推送")
        return

    rows = _users_to_remind()
    logger.info("待提醒订阅数：%s", len(rows))

    for _user_id, subscription in rows:
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(
                    {"title": "今天还没开始哦", "body": "花 10 分钟读几个单词吧"}
                ),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.info("推送失败 status=%s", status)
            if status in (404, 410):
                with SessionLocal() as db:
                    record = db.execute(
                        select(PushSubscription).where(
                            PushSubscription.endpoint == subscription.get("endpoint")
                        )
                    ).scalar_one_or_none()
                    if record is not None:
                        db.delete(record)
                        db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("推送异常")


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        send_daily_reminders,
        trigger=CronTrigger(hour=19, minute=0, timezone=settings.app_timezone),
        id="daily_reminder",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return scheduler
