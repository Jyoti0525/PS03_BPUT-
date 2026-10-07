"""data origin on every patient and encounter (G8): SYNTHETIC or PUBLIC_SAMPLE

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-07 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('patients', sa.Column('data_origin', sa.String(16), nullable=False, server_default='SYNTHETIC'))
    op.add_column('encounters', sa.Column('data_origin', sa.String(16), nullable=False, server_default='SYNTHETIC'))


def downgrade() -> None:
    op.drop_column('encounters', 'data_origin')
    op.drop_column('patients', 'data_origin')
