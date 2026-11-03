"""
Synthetic demo data seeder (docs/demo.md).

Thin CLI wrapper around `app.services.demo_service.ensure_demo_project`,
which builds a real local Git repository with engineered properties and
runs it through the real ingestion + analysis pipeline (the same code path
a real repository would use) — so every number the demo shows is genuinely
computed, not hard-coded.

Idempotent: reuses the existing fully-analyzed demo project when one is
available instead of creating duplicates. Pass `--force` to build a fresh
demo workspace regardless.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: F401,E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.services.demo_service import build_demo_repo, ensure_demo_project  # noqa: E402
from app.models.project import Project, Repository  # noqa: E402
from app.services.analysis_pipeline import run_analysis  # noqa: E402


def main(force: bool = False) -> None:
    Base.metadata.create_all(engine)
    db: Session = SessionLocal()
    try:
        if force:
            repo_path = build_demo_repo()
            project = Project(
                name="CodeRadar Demo",
                description="Synthetic demo workspace (10 developers, 8 modules).",
                is_demo=True,
            )
            db.add(project)
            db.flush()
            db.add(Repository(project_id=project.id, url=repo_path, provider="local"))
            db.commit()
            run = run_analysis(db, project)
            print(f"Seeded demo project {project.id} — analysis run {run.id} status: {run.status}")
            if run.status != "complete":
                print(f"Warning: {run.error_message}")
            return

        result = ensure_demo_project(db)
        action = "Seeded demo project" if result["created"] else "Reusing demo project"
        print(f"{action} {result['project_id']} — analysis run {result['analysis_run_id']} status: {result['status']}")
    finally:
        db.close()


if __name__ == "__main__":
    main(force="--force" in sys.argv)
