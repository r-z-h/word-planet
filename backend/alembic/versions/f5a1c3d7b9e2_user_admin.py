"""users.is_admin

Revision ID: f5a1c3d7b9e2
Revises: b1f7c3d9e5a2
Create Date: 2026-10-31
"""

from alembic import op
import sqlalchemy as sa

revision = 'f5a1c3d7b9e2'
down_revision = 'b1f7c3d9e5a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_admin')
