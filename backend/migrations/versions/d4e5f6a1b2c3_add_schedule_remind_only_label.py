"""add remind_only and label to schedules table

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-06-05 00:00:00.000000

Adds two columns to the schedules table:
  - label: optional human-readable name for the schedule (e.g. "Sleep mode")
  - remind_only: if True the scheduler emits a Socket.IO popup instead of
    auto-executing the MQTT command
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a1b2c3'
down_revision = 'c3d4e5f6a1b2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('schedules', sa.Column('label', sa.String(length=100), nullable=True))
    op.add_column('schedules', sa.Column('remind_only', sa.Boolean(), nullable=False, server_default=sa.text('0')))


def downgrade():
    op.drop_column('schedules', 'remind_only')
    op.drop_column('schedules', 'label')
