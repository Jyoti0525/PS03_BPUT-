"""patient load per facility (F2): how many follow-up questions the kiosk asks

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-07 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0013'
down_revision: str | None = '0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('facilities', sa.Column('patient_load', sa.String(8), nullable=False, server_default='normal'))


def downgrade() -> None:
    op.drop_column('facilities', 'patient_load')
