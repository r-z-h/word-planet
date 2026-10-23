import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    account: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str | None] = mapped_column(String(2), nullable=True)
    has_tested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("level IN ('L1','L2','L3')", name="ck_users_level"),
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint("level", "sort_order", name="uq_kp_level_sort"),
        CheckConstraint("level IN ('L1','L2','L3')", name="ck_kp_level"),
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id"), nullable=False
    )
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    set_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_quiz: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("knowledge_point_id", "stem", name="uq_question_kp_stem"),
        CheckConstraint("difficulty BETWEEN 1 AND 3", name="ck_question_difficulty"),
    )


class Progress(Base):
    __tablename__ = "progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    current_knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id"), nullable=True
    )
    completed_knowledge_points: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # 当前未作答、下次进入答题页要恢复的那道题
    last_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=True
    )
    # 水平测试里已经出过的题，学习阶段优先避开
    test_seen_question_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False
    )
    question_type: Mapped[str] = mapped_column(String(32), nullable=False, default="question")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_attempt_user_idem"),
    )


class Streak(Base):
    __tablename__ = "streaks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_study_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class WrongQuestion(Base):
    __tablename__ = "wrong_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False
    )
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    consecutive_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_wrong_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_wrong_user_question"),
    )


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_value: Mapped[int] = mapped_column(Integer, nullable=False)


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("badges.id"), nullable=False
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_achievement_user_badge"),
    )


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "task_date", name="uq_daily_user_date"),
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    subscription: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
