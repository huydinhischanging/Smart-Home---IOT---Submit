"""add device_type and metadata_json to device table

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-05-15 00:00:00.000000

These two columns were defined in the Device SQLAlchemy model but were
absent from the initial migration, causing device creation to fail with
an "Unknown column" MySQL error.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a1b2'
down_revision = 'b2c3d4e5f6a1'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col['name'] for col in inspector.get_columns('device')}

    if 'device_type' not in existing:
        op.add_column(
            'device',
            sa.Column('device_type', sa.String(50), nullable=True),
        )
    if 'metadata_json' not in existing:
        op.add_column(
            'device',
            sa.Column(
                'metadata_json',
                sa.JSON,
                nullable=False,
                server_default='{}',
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col['name'] for col in inspector.get_columns('device')}
    if 'metadata_json' in existing:
        op.drop_column('device', 'metadata_json')
    if 'device_type' in existing:
        op.drop_column('device', 'device_type')
