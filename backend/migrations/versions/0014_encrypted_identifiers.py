"""encryption at rest: patient identifiers become text (Fernet tokens), phone found by a keyed hash

The values themselves are encrypted by app.crypto.encrypt_existing at start-up (it needs the data key).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-07 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0014'
down_revision: str | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for col in ('name', 'phone', 'village'):
        op.alter_column('patients', col, type_=sa.Text())
    op.alter_column('consents', 'proxy_name', type_=sa.Text())
    op.add_column('patients', sa.Column('phone_hash', sa.String(64), nullable=True))
    op.create_index('ix_patients_phone_hash', 'patients', ['phone_hash'])
    op.drop_index('ix_patients_phone', table_name='patients')


def downgrade() -> None:
    op.create_index('ix_patients_phone', 'patients', ['phone'])
    op.drop_index('ix_patients_phone_hash', table_name='patients')
    op.drop_column('patients', 'phone_hash')
