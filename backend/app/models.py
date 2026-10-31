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
    max_level: Mapped[str | None] = mapped_column(String(2), nullable=True)
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
    # 是否计入「本级能力测试」的门槛（字母表、听力理解这类题量固定的不计）
    counts_for_gate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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


class SetProgress(Base):
    """用户完成某一套的记录。重复练习不再新增行，也不改统计。"""

    __tablename__ = "set_progress"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id"), nullable=False
    )
    set_no: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- 三层奖励缓存（v2，见 游戏设计.md 14.1） ---
    # 只增不减；= question_flowers 里属于该套的行数
    flowers_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 已兑出的星星数（0-5）
    stars_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 该套是否已产出过徽记（0/1）
    medals_granted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 纯练星球也用它：该套是否「全部答对」
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", "set_no", name="uq_set_progress"),
    )


class QuestionFlower(Base):
    """花账本，三层奖励的唯一真相。

    UNIQUE(user_id, question_id) 保证每题只拿一次花（防刷、防重复补花）。
    set_no 冗余存，便于按套汇总。
    """

    __tablename__ = "question_flowers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False
    )
    set_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="main")  # main|practice
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_question_flower"),
        CheckConstraint("source IN ('main','practice')", name="ck_question_flower_source"),
    )


class PlanetMedal(Base):
    """按星球累计徽记，地图徽标与「全收集」判定用。"""

    __tablename__ = "planet_medals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id"), nullable=False
    )
    medals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_planet_medal"),
    )


class FlowerExchange(Base):
    """兑换流水。「今日星」口径靠它（当天 to_kind='star' 的 amount 之和）。"""

    __tablename__ = "flower_exchanges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    from_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # flower|star
    to_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # star|medal
    set_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id"), nullable=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("from_kind IN ('flower','star')", name="ck_exchange_from"),
        CheckConstraint("to_kind IN ('star','medal')", name="ck_exchange_to"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_exchange_user_idem"),
    )



class LevelTest(Base):
    """一次级别能力测试的结果。level 指被测试的等级（测本级内容）。"""

    __tablename__ = "level_tests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Word(Base):
    """词典页用的单词条目（来源：ECDICT + 人教版词表）。"""

    __tablename__ = "words"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    word: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    grade: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phonetic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    senses: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    definition_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_phrase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
