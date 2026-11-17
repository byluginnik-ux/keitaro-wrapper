"""Mark a stream that an unfinished task is publishing.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("streams", sa.Column("publishing_task_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("streams", "publishing_task_id")
