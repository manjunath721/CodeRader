"""add auth audit and rescan fields

Revision ID: d4e1f56a7890
Revises: 9fd52e3c4171
Create Date: 2026-11-04 12:00:00.000000

Adds users, project_members, and audit_logs tables for security and RBAC.
Adds rescan_interval_hours to projects.
Adds rescan_type and commit_sha to analysis_runs.
Adds lines_of_code to files.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID


# revision identifiers, used by Alembic.
revision: str = 'd4e1f56a7890'
down_revision: Union[str, Sequence[str], None] = '9fd52e3c4171'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Project members table
    op.create_table(
        'project_members',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('project_id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='owner'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_member')
    )
    op.create_index(op.f('ix_project_members_project_id'), 'project_members', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_members_user_id'), 'project_members', ['user_id'], unique=False)

    # Audit logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('actor_id', GUID(), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)

    # New columns
    op.add_column('projects', sa.Column('rescan_interval_hours', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('analysis_runs', sa.Column('rescan_type', sa.String(length=30), nullable=False, server_default='full'))
    op.add_column('analysis_runs', sa.Column('commit_sha', sa.String(length=64), nullable=True))
    op.add_column('files', sa.Column('lines_of_code', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('files', 'lines_of_code')
    op.drop_column('analysis_runs', 'commit_sha')
    op.drop_column('analysis_runs', 'rescan_type')
    op.drop_column('projects', 'rescan_interval_hours')

    op.drop_index(op.f('ix_audit_logs_actor_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index(op.f('ix_project_members_user_id'), table_name='project_members')
    op.drop_index(op.f('ix_project_members_project_id'), table_name='project_members')
    op.drop_table('project_members')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
