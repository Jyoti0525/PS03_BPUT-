"""referrals name the receiving facility, whose doctors see them under Incoming

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-10 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0015'
down_revision: str | None = '0014'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('referrals', sa.Column('to_facility_id', sa.String(64), sa.ForeignKey('facilities.id'), nullable=True))
    op.create_index('ix_referrals_to_facility_id', 'referrals', ['to_facility_id'])


def downgrade() -> None:
    op.drop_index('ix_referrals_to_facility_id', table_name='referrals')
    op.drop_column('referrals', 'to_facility_id')
