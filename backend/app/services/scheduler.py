import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import app.core.db as db_module
from app.models.analysis import AnalysisRun
from app.models.project import Project
from app.services.job_worker import enqueue_analysis_job

logger = logging.getLogger(__name__)
_scheduler_thread = None
_stop_event = threading.Event()


def _check_and_trigger_scheduled_rescans() -> None:
    db = db_module.SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        projects = db.query(Project).filter(Project.rescan_interval_hours > 0).all()
        for p in projects:
            interval = timedelta(hours=p.rescan_interval_hours)
            # Find latest run
            latest_run = (
                db.query(AnalysisRun)
                .filter(AnalysisRun.project_id == p.id)
                .order_by(AnalysisRun.created_at.desc())
                .first()
            )
            # If active run in progress, do not overlap
            if latest_run and latest_run.status in ("pending", "running"):
                continue

            is_due = False
            if not latest_run:
                is_due = True
            elif latest_run.completed_at and (now - latest_run.completed_at) >= interval:
                is_due = True

            if is_due:
                logger.info("Triggering scheduled rescan for project %s (%s)", p.name, p.id)
                placeholder = AnalysisRun(
                    project_id=p.id,
                    status="pending",
                    stage_status={},
                    scan_mode="incremental",
                    rescan_type="scheduled",
                    started_at=now,
                )
                db.add(placeholder)
                db.commit()
                db.refresh(placeholder)
                enqueue_analysis_job(p.id, placeholder.id)
    except Exception as e:
        logger.error("Error during scheduled rescan check: %s", e)
    finally:
        db.close()


def _scheduler_loop() -> None:
    logger.info("CodeRadar rescan scheduler started.")
    while not _stop_event.is_set():
        try:
            _check_and_trigger_scheduled_rescans()
        except Exception as e:
            logger.error("Scheduler loop error: %s", e)
        # Sleep for 60 seconds or until stopped
        _stop_event.wait(60.0)


def start_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _stop_event.clear()
        _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="coderadar_scheduler")
        _scheduler_thread.start()


def stop_scheduler() -> None:
    _stop_event.set()
