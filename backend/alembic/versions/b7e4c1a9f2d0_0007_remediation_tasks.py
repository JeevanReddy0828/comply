"""0007 remediation tasks

Revision ID: b7e4c1a9f2d0
Revises: d19735c24495
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e4c1a9f2d0'
down_revision: Union[str, None] = 'd19735c24495'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'remediation_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('system_id', sa.String(length=36), nullable=False),
        sa.Column('control_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('source_gap_reason', sa.String(length=32), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(length=36), nullable=True),
        sa.Column('resolution', sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['system_id'], ['ai_systems.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_remediation_tasks_org_id', 'remediation_tasks', ['org_id'])
    op.create_index('ix_remediation_tasks_system_id', 'remediation_tasks', ['system_id'])
    op.create_index('ix_remediation_tasks_control_id', 'remediation_tasks', ['control_id'])
    op.create_index('ix_remediation_tasks_system', 'remediation_tasks', ['org_id', 'system_id'])
    # At most one non-RESOLVED task per (system, control): preserves resolved history
    # while preventing duplicate open work.
    op.create_index(
        'uq_open_task_per_control',
        'remediation_tasks',
        ['system_id', 'control_id'],
        unique=True,
        postgresql_where=sa.text("status <> 'RESOLVED'"),
    )


def downgrade() -> None:
    op.drop_index('uq_open_task_per_control', table_name='remediation_tasks')
    op.drop_index('ix_remediation_tasks_system', table_name='remediation_tasks')
    op.drop_index('ix_remediation_tasks_control_id', table_name='remediation_tasks')
    op.drop_index('ix_remediation_tasks_system_id', table_name='remediation_tasks')
    op.drop_index('ix_remediation_tasks_org_id', table_name='remediation_tasks')
    op.drop_table('remediation_tasks')
