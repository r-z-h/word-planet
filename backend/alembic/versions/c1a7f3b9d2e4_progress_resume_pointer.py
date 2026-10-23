"""progress 增加 last_question_id / test_seen_question_ids

Revision ID: c1a7f3b9d2e4
Revises: 732371b2903b
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c1a7f3b9d2e4"
down_revision = "732371b2903b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "progress",
        sa.Column("last_question_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "progress",
        sa.Column(
            "test_seen_question_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_foreign_key(
        "fk_progress_last_question",
        "progress",
        "questions",
        ["last_question_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_progress_last_question", "progress", type_="foreignkey")
    op.drop_column("progress", "test_seen_question_ids")
    op.drop_column("progress", "last_question_id")
