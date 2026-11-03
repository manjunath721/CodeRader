"""prevent concurrent analysis runs per project

Revision ID: 9fd52e3c4171
Revises: c30b4075597f
Create Date: 2026-10-01 01:30:25.262402

A plain application-level "check then insert" cannot prevent two concurrent
POST /analyze requests from both passing the check and starting two runs
against the same project's data (classic TOCTOU race). A partial unique
index is the actual safety mechanism: the database itself rejects a second
pending/running row for the same project_id, no matter how the race lands.
Supported natively by both Postgres and SQLite (3.8.0+), so no batch mode
needed here — this is a plain CREATE INDEX, not a column/constraint ALTER.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9fd52e3c4171'
down_revision: Union[str, Sequence[str], None] = 'c30b4075597f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_one_active_run_per_project"


def upgrade() -> None:
    op.execute(
        f"CREATE UNIQUE INDEX {INDEX_NAME} ON analysis_runs (project_id) "
        f"WHERE status IN ('pending', 'running')"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX {INDEX_NAME}")
