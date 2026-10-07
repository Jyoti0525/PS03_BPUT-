"""arrival check-in (C3): when the patient reached the facility, and kiosk links meant for filling in from home

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db  # noqa: F401  (custom column types)


revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('encounters', sa.Column('arrived_at', app.db.UTCDateTime(timezone=True), nullable=True))
    op.execute("UPDATE encounters SET arrived_at = created_at")  # every earlier intake was made at the facility
    op.add_column('kiosk_links', sa.Column('for_home', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('kiosk_links', 'for_home')
    op.drop_column('encounters', 'arrived_at')
