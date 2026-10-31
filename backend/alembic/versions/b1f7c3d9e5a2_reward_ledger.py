"""三层奖励：花账本 / 星球徽记 / 兑换流水，并给 set_progress 加 4 列

Revision ID: b1f7c3d9e5a2
Revises: a5e1f7b9c4d6
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1f7c3d9e5a2"
down_revision = "a5e1f7b9c4d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- set_progress 加 4 列（只增不减的缓存） ---
    op.add_column(
        "set_progress",
        sa.Column("flowers_earned", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "set_progress",
        sa.Column("stars_earned", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "set_progress",
        sa.Column("medals_granted", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "set_progress",
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # --- 花账本：每题只记一次 ---
    op.create_table(
        "question_flowers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questions.id"),
            nullable=False,
        ),
        sa.Column("set_no", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="main"),
        sa.Column("earned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "question_id", name="uq_question_flower"),
        sa.CheckConstraint("source IN ('main','practice')", name="ck_question_flower_source"),
    )

    # --- 按星球累计徽记 ---
    op.create_table(
        "planet_medals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "knowledge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id"),
            nullable=False,
        ),
        sa.Column("medals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "knowledge_point_id", name="uq_planet_medal"),
    )

    # --- 兑换流水（今日星口径） ---
    op.create_table(
        "flower_exchanges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("from_kind", sa.String(16), nullable=False),
        sa.Column("to_kind", sa.String(16), nullable=False),
        sa.Column("set_no", sa.Integer(), nullable=True),
        sa.Column(
            "knowledge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id"),
            nullable=True,
        ),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_exchange_user_idem"),
        sa.CheckConstraint("from_kind IN ('flower','star')", name="ck_exchange_from"),
        sa.CheckConstraint("to_kind IN ('star','medal')", name="ck_exchange_to"),
    )


def downgrade() -> None:
    op.drop_table("flower_exchanges")
    op.drop_table("planet_medals")
    op.drop_table("question_flowers")
    op.drop_column("set_progress", "is_complete")
    op.drop_column("set_progress", "medals_granted")
    op.drop_column("set_progress", "stars_earned")
    op.drop_column("set_progress", "flowers_earned")
