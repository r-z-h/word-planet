"""words 词典表

Revision ID: a5e1f7b9c4d6
Revises: f4d0e6a8b3c5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a5e1f7b9c4d6"
down_revision = "f4d0e6a8b3c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "words",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("word", sa.String(128), nullable=False, unique=True),
        sa.Column("display", sa.String(128), nullable=False),
        sa.Column("level", sa.String(2), nullable=False),
        sa.Column("grade", sa.String(32), nullable=False, server_default=""),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phonetic", sa.String(128), nullable=True),
        sa.Column("senses", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("definition_en", sa.Text(), nullable=True),
        sa.Column("is_phrase", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_words_level_order", "words", ["level", "order_index"])


def downgrade() -> None:
    op.drop_index("ix_words_level_order", table_name="words")
    op.drop_table("words")
