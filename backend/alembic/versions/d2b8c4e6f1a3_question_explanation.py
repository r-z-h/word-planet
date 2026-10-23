"""questions 增加 explanation（题目解析）

Revision ID: d2b8c4e6f1a3
Revises: c1a7f3b9d2e4
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa

revision = "d2b8c4e6f1a3"
down_revision = "c1a7f3b9d2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("questions", "explanation")
