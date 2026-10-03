"""file extraction results (OCR / text layer lab rows)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from sqlalchemy.dialects import postgresql

import app.db  # noqa: F401  (custom column types)


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('files', sa.Column('extraction', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True))


def downgrade() -> None:
    op.drop_column('files', 'extraction')
