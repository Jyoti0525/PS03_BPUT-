"""facility regional calendar and cadre overrides (F5)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-05 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from sqlalchemy.dialects import postgresql

import app.db  # noqa: F401  (custom column types)


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('facilities', sa.Column('region_config', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True))


def downgrade() -> None:
    op.drop_column('facilities', 'region_config')
