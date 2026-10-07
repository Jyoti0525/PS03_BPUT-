"""reminder calls (E6): one row per simulated call, with every line said and heard

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-06 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from sqlalchemy.dialects import postgresql

import app.db  # noqa: F401  (custom column types)


revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'calls',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('reminder_id', sa.String(64), sa.ForeignKey('reminders.id'), nullable=False),
        sa.Column('patient_id', sa.String(64), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('facility_id', sa.String(64), sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('started_by', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('operator', sa.String(8), nullable=False),
        sa.Column('programme', sa.String(12), nullable=False),
        sa.Column('language', sa.String(8), nullable=False),
        sa.Column('audience', sa.String(8), nullable=False),
        sa.Column('plan', JSON, nullable=False),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('reprompts', sa.Integer(), nullable=False),
        sa.Column('turns', JSON, nullable=False),
        sa.Column('status', sa.String(8), nullable=False),
        sa.Column('outcome', sa.String(16), nullable=True),
        sa.Column('red_flags', JSON, nullable=True),
        sa.Column('notes', JSON, nullable=True),
        sa.Column('alert_id', sa.String(64), nullable=True),
        sa.Column('started_at', app.db.UTCDateTime(timezone=True), nullable=False),
        sa.Column('ended_at', app.db.UTCDateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_calls_reminder_id', 'calls', ['reminder_id'])
    op.create_index('ix_calls_patient_id', 'calls', ['patient_id'])
    op.create_index('ix_calls_facility_id', 'calls', ['facility_id'])


def downgrade() -> None:
    op.drop_index('ix_calls_facility_id', 'calls')
    op.drop_index('ix_calls_patient_id', 'calls')
    op.drop_index('ix_calls_reminder_id', 'calls')
    op.drop_table('calls')
