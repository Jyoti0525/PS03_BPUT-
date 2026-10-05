"""alerts (capacity, fever cluster, missed visit) and maternal follow-up fields on reminders

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-06 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from sqlalchemy.dialects import postgresql

import app.db  # noqa: F401  (custom column types)


revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('facility_id', sa.String(64), sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('key', sa.String(120), nullable=False),
        sa.Column('to_role', sa.String(20), nullable=False),
        sa.Column('assigned_to', sa.String(64), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('detail', JSON, nullable=False),
        sa.Column('status', sa.String(14), nullable=False),
        sa.Column('raised_at', app.db.UTCDateTime(timezone=True), nullable=False),
        sa.Column('updated_at', app.db.UTCDateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_by', sa.String(200), nullable=True),
        sa.Column('acknowledged_at', app.db.UTCDateTime(timezone=True), nullable=True),
        sa.Column('ack_note', sa.Text(), nullable=True),
        sa.Column('resolved_at', app.db.UTCDateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_alerts_facility_id', 'alerts', ['facility_id'])
    op.create_index('ix_alerts_status', 'alerts', ['status'])
    op.create_index('ix_alerts_open', 'alerts', ['facility_id', 'kind', 'key', 'status'])
    op.add_column('reminders', sa.Column('facility_id', sa.String(64), sa.ForeignKey('facilities.id'), nullable=True))
    op.add_column('reminders', sa.Column('assigned_to', sa.String(64), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('reminders', sa.Column('phone_belongs_to', sa.String(12), nullable=True))
    op.add_column('reminders', sa.Column('encounter_id', sa.String(64), sa.ForeignKey('encounters.id'), nullable=True))
    op.add_column('reminders', sa.Column('missed_at', app.db.UTCDateTime(timezone=True), nullable=True))
    op.add_column('reminders', sa.Column('attempts', JSON, nullable=True))
    op.add_column('reminders', sa.Column('resolved_at', app.db.UTCDateTime(timezone=True), nullable=True))
    op.create_index('ix_reminders_facility_id', 'reminders', ['facility_id'])
    op.create_index('ix_reminders_assigned_to', 'reminders', ['assigned_to'])


def downgrade() -> None:
    op.drop_index('ix_reminders_assigned_to', 'reminders')
    op.drop_index('ix_reminders_facility_id', 'reminders')
    for c in ('resolved_at', 'attempts', 'missed_at', 'encounter_id', 'phone_belongs_to', 'assigned_to', 'facility_id'):
        op.drop_column('reminders', c)
    op.drop_index('ix_alerts_open', 'alerts')
    op.drop_index('ix_alerts_status', 'alerts')
    op.drop_index('ix_alerts_facility_id', 'alerts')
    op.drop_table('alerts')
