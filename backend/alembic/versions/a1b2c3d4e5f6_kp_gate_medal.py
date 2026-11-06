"""knowledge_points 增加星球徽记 / 门槛配置

Revision ID: a1b2c3d4e5f6
Revises: f5a1c3d7b9e2
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f5a1c3d7b9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_points",
        sa.Column("medal_name", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("medal_icon", sa.String(8), nullable=False, server_default=""),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("gate_mode", sa.String(16), nullable=False, server_default="medals"),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("gate_required", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "knowledge_points",
        sa.Column("produces_flowers", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    for col in ("medal_name", "medal_icon", "gate_mode", "gate_required", "produces_flowers"):
        op.drop_column("knowledge_points", col)
