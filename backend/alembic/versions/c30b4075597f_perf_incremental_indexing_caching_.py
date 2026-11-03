"""perf incremental indexing caching concurrency indexes

Revision ID: c30b4075597f
Revises: f63d8f97059d
Create Date: 2026-10-01 01:28:53.993603

Perf/correctness work: incremental indexing state on Repository, content-hash
analysis caching + upsert keys on File, idempotent-retry key on Commit,
upsert keys on the activity aggregate tables, and the FK indexes the original
schema was missing. Uses batch_alter_table throughout so this migration runs
unchanged on SQLite (used in CI/tests) and Postgres (production) alike.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c30b4075597f'
down_revision: Union[str, Sequence[str], None] = 'f63d8f97059d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('analysis_runs') as batch_op:
        batch_op.add_column(sa.Column('progress', sa.JSON(), nullable=False, server_default='{}'))
        batch_op.add_column(sa.Column('scan_mode', sa.String(length=20), nullable=False, server_default='full'))
        batch_op.add_column(sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index(batch_op.f('ix_analysis_runs_project_id'), ['project_id'], unique=False)

    with op.batch_alter_table('commits') as batch_op:
        batch_op.create_index(batch_op.f('ix_commits_repository_id'), ['repository_id'], unique=False)
        batch_op.create_unique_constraint('uq_commit_repo_hash', ['repository_id', 'hash'])

    with op.batch_alter_table('developer_file_activity') as batch_op:
        batch_op.create_index(batch_op.f('ix_developer_file_activity_developer_id'), ['developer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_developer_file_activity_file_id'), ['file_id'], unique=False)
        batch_op.create_unique_constraint('uq_dev_file_activity', ['developer_id', 'file_id'])

    with op.batch_alter_table('developer_module_activity') as batch_op:
        batch_op.create_index(batch_op.f('ix_developer_module_activity_developer_id'), ['developer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_developer_module_activity_module_id'), ['module_id'], unique=False)
        batch_op.create_unique_constraint('uq_dev_module_activity', ['developer_id', 'module_id'])

    with op.batch_alter_table('files') as batch_op:
        batch_op.add_column(sa.Column('content_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('analyzer_version', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('import_targets', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.create_index(batch_op.f('ix_files_content_hash'), ['content_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_files_repository_id'), ['repository_id'], unique=False)
        batch_op.create_unique_constraint('uq_file_repo_path', ['repository_id', 'path'])

    with op.batch_alter_table('module_dependencies') as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=20), nullable=False, server_default='import'))
        batch_op.create_index(batch_op.f('ix_module_dependencies_depends_on_module_id'), ['depends_on_module_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_module_dependencies_module_id'), ['module_id'], unique=False)
        batch_op.create_unique_constraint('uq_module_dependency_edge', ['module_id', 'depends_on_module_id'])

    with op.batch_alter_table('modules') as batch_op:
        batch_op.create_index(batch_op.f('ix_modules_repository_id'), ['repository_id'], unique=False)
        batch_op.create_unique_constraint('uq_module_repo_path', ['repository_id', 'path_prefix'])

    with op.batch_alter_table('repositories') as batch_op:
        batch_op.add_column(sa.Column('last_indexed_commit_sha', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('last_indexed_branch', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('scan_mode', sa.String(length=20), nullable=False, server_default='full'))


def downgrade() -> None:
    with op.batch_alter_table('repositories') as batch_op:
        batch_op.drop_column('scan_mode')
        batch_op.drop_column('last_indexed_branch')
        batch_op.drop_column('last_indexed_commit_sha')

    with op.batch_alter_table('modules') as batch_op:
        batch_op.drop_constraint('uq_module_repo_path', type_='unique')
        batch_op.drop_index(batch_op.f('ix_modules_repository_id'))

    with op.batch_alter_table('module_dependencies') as batch_op:
        batch_op.drop_constraint('uq_module_dependency_edge', type_='unique')
        batch_op.drop_index(batch_op.f('ix_module_dependencies_module_id'))
        batch_op.drop_index(batch_op.f('ix_module_dependencies_depends_on_module_id'))
        batch_op.drop_column('source')

    with op.batch_alter_table('files') as batch_op:
        batch_op.drop_constraint('uq_file_repo_path', type_='unique')
        batch_op.drop_index(batch_op.f('ix_files_repository_id'))
        batch_op.drop_index(batch_op.f('ix_files_content_hash'))
        batch_op.drop_column('import_targets')
        batch_op.drop_column('analyzer_version')
        batch_op.drop_column('content_hash')

    with op.batch_alter_table('developer_module_activity') as batch_op:
        batch_op.drop_constraint('uq_dev_module_activity', type_='unique')
        batch_op.drop_index(batch_op.f('ix_developer_module_activity_module_id'))
        batch_op.drop_index(batch_op.f('ix_developer_module_activity_developer_id'))

    with op.batch_alter_table('developer_file_activity') as batch_op:
        batch_op.drop_constraint('uq_dev_file_activity', type_='unique')
        batch_op.drop_index(batch_op.f('ix_developer_file_activity_file_id'))
        batch_op.drop_index(batch_op.f('ix_developer_file_activity_developer_id'))

    with op.batch_alter_table('commits') as batch_op:
        batch_op.drop_constraint('uq_commit_repo_hash', type_='unique')
        batch_op.drop_index(batch_op.f('ix_commits_repository_id'))

    with op.batch_alter_table('analysis_runs') as batch_op:
        batch_op.drop_index(batch_op.f('ix_analysis_runs_project_id'))
        batch_op.drop_column('cancel_requested')
        batch_op.drop_column('scan_mode')
        batch_op.drop_column('progress')
