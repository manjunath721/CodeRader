import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

import app.core.db as db_module
from app.models.analysis import AnalysisRun
from app.models.project import Project
from app.services.analysis_pipeline import run_analysis

logger = logging.getLogger(__name__)

# Concurrency limits: max 3 worker threads across the application,
# with per-project mutual exclusion locks to prevent concurrent runs on the same project.
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="coderadar_worker")
_project_locks: dict[uuid.UUID, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_project_lock(project_id: uuid.UUID) -> threading.Lock:
    with _locks_guard:
        if project_id not in _project_locks:
            _project_locks[project_id] = threading.Lock()
        return _project_locks[project_id]


def _execute_analysis_task(project_id: uuid.UUID, run_id: uuid.UUID) -> None:
    lock = _get_project_lock(project_id)
    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.warning("Analysis already in progress for project %s; skipping concurrent execution", project_id)
        return

    db: Session = db_module.SessionLocal()
    try:
        project = db.get(Project, project_id)
        run = db.get(AnalysisRun, run_id)
        if project and run:
            logger.info("Starting background analysis for project %s (run %s)", project_id, run_id)
            run_analysis(db, project, run=run)
    except Exception as e:
        logger.exception("Error executing background analysis for project %s, run %s: %s", project_id, run_id, e)
    finally:
        db.close()
        lock.release()


def enqueue_analysis_job(project_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """Submits analysis run to durable worker pool."""
    _executor.submit(_execute_analysis_task, project_id, run_id)


def recover_stale_runs_on_startup() -> None:
    """
    On application boot, mark any orphan runs that were left in 'pending' or 'running'
    when the previous process exited as 'failed'.
    """
    try:
        db = db_module.SessionLocal()
        orphans = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.status.in_(["pending", "running"]))
            .all()
        )
        if orphans:
            now = datetime.now(timezone.utc)
            for r in orphans:
                r.status = "failed"
                r.error_message = "Analysis interrupted by server restart. Please retry rescan."
                r.completed_at = now
                db.add(r)
            db.commit()
            logger.info("Recovered and cleaned up %d orphan analysis runs from prior shutdown", len(orphans))
    except Exception as e:
        logger.warning("Could not recover orphan runs on startup: %s", e)
    finally:
        db.close()
