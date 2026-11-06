"""knowledge_points.medal_icon 加长到 128（支持图片路径）

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-06
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_points",
        "medal_icon",
        existing_type=sa.String(length=8),
        type_=sa.String(length=128),
        existing_nullable=False,
        existing_server_default="",
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_points",
        "medal_icon",
        existing_type=sa.String(length=128),
        type_=sa.String(length=8),
        existing_nullable=False,
        existing_server_default="",
    )
