"""questions 增加 set_no（套号），用于一个知识点下多套题

Revision ID: e3c9d5f7a2b4
Revises: d2b8c4e6f1a3
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa

revision = "e3c9d5f7a2b4"
down_revision = "d2b8c4e6f1a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("set_no", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_questions_kp_set", "questions", ["knowledge_point_id", "set_no"])


def downgrade() -> None:
    op.drop_index("ix_questions_kp_set", table_name="questions")
    op.drop_column("questions", "set_no")
