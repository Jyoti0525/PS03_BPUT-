"""staff duty status (front-desk time management)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db  # noqa: F401  (custom column types)

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("on_duty", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("users", sa.Column("duty_changed_at", app.db.UTCDateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "duty_changed_at")
    op.drop_column("users", "on_duty")
