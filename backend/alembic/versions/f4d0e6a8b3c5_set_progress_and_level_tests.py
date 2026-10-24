"""套进度与能力测试

Revision ID: f4d0e6a8b3c5
Revises: e3c9d5f7a2b4
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f4d0e6a8b3c5"
down_revision = "e3c9d5f7a2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 已解锁的最高等级（回访低等级时 level 会变，max_level 不变）
    op.add_column("users", sa.Column("max_level", sa.String(2), nullable=True))
    op.execute("UPDATE users SET max_level = level WHERE max_level IS NULL AND level IS NOT NULL")

    # 是否计入升级门槛（字母表、听力理解不计）
    op.add_column(
        "knowledge_points",
        sa.Column("counts_for_gate", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "set_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "knowledge_point_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id"),
            nullable=False,
        ),
        sa.Column("set_no", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "knowledge_point_id", "set_no", name="uq_set_progress"),
    )

    op.create_table(
        "level_tests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("level", sa.String(2), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("level_tests")
    op.drop_table("set_progress")
    op.drop_column("knowledge_points", "counts_for_gate")
    op.drop_column("users", "max_level")
