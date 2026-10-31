import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import (
    achievement,
    auth,
    lesson,
    level_test,
    practice,
    progress,
    pronunciation,
    push,
    question,
    report,
    reward,
    test,
    words,
    wrong,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("word_planet")

_scheduler = None


def _start_scheduler():
    global _scheduler
    from .scheduler import build_scheduler

    _scheduler = build_scheduler()
    _scheduler.start()
    logger.info("APScheduler started")


def _stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.enable_scheduler:
        _start_scheduler()
    else:
        logger.info("APScheduler disabled (ENABLE_SCHEDULER=0)")
    yield
    if settings.enable_scheduler:
        _stop_scheduler()


app = FastAPI(title="Word Planet API", version="1.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    test.router,
    question.router,
    progress.router,
    wrong.router,
    achievement.router,
    report.router,
    pronunciation.router,
    push.router,
    practice.router,
    lesson.router,
    level_test.router,
    words.router,
    reward.router,
):
    app.include_router(router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "timezone": settings.app_timezone}
