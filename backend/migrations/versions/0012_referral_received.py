"""referral closed only when care is received (E4): due time and who confirmed receipt

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-07 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db  # noqa: F401  (custom column types)

revision: str = '0012'
down_revision: str | None = '0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('referrals', sa.Column('due_at', app.db.UTCDateTime(timezone=True), nullable=True))
    op.add_column('referrals', sa.Column('received_at', app.db.UTCDateTime(timezone=True), nullable=True))
    op.add_column('referrals', sa.Column('received_by', sa.String(200), nullable=True))
    op.add_column('referrals', sa.Column('received_note', sa.Text(), nullable=True))
    op.add_column('referrals', sa.Column('received_via', sa.String(16), nullable=True))


def downgrade() -> None:
    for c in ('received_via', 'received_note', 'received_by', 'received_at', 'due_at'):
        op.drop_column('referrals', c)
