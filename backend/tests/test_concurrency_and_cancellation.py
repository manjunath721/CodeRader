from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.core.db as db_module
from app.core.db import Base, get_db
from app.main import app
from app.models.analysis import AnalysisRun
from app.models.project import Project


def _make_client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db_module.SessionLocal = TestSession
    return TestClient(app), TestSession


def test_cannot_start_two_analyses_for_the_same_project_concurrently(synthetic_repo):
    client, TestSession = _make_client()
    try:
        project = client.post("/api/projects", json={"name": "Concurrency Test"}).json()
        client.post(
            f"/api/projects/{project['id']}/repositories",
            json={"url": synthetic_repo, "provider": "local"},
        )

        # Manually insert a still-running run to simulate an in-flight analysis,
        # bypassing the background task so we control timing precisely.
        db = TestSession()
        db.add(AnalysisRun(project_id=project["id"], status="running", stage_status={}))
        db.commit()
        db.close()

        r = client.post(f"/api/projects/{project['id']}/analyze")
        assert r.status_code == 409
        assert r.json()["code"] == "ANALYSIS_ALREADY_RUNNING"
    finally:
        app.dependency_overrides.clear()


def test_database_constraint_is_the_real_guard_not_just_the_precheck(synthetic_repo):
    """Even if two requests both raced past the application-level pre-check,
    the partial unique index must still reject the second INSERT."""
    client, TestSession = _make_client()
    try:
        project = client.post("/api/projects", json={"name": "Race Test"}).json()

        db1 = TestSession()
        db2 = TestSession()
        run1 = AnalysisRun(project_id=project["id"], status="running", stage_status={})
        db1.add(run1)
        db1.commit()

        run2 = AnalysisRun(project_id=project["id"], status="running", stage_status={})
        db2.add(run2)
        try:
            db2.commit()
            raised = False
        except Exception:
            db2.rollback()
            raised = True
        assert raised, "the partial unique index should have rejected a second active run"
        db1.close()
        db2.close()
    finally:
        app.dependency_overrides.clear()


def test_cancel_sets_flag_and_pipeline_stops_cleanly(synthetic_repo):
    from app.models.project import Repository
    from app.services.analysis_pipeline import run_analysis

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    project = Project(name="Cancel Test")
    db.add(project)
    db.flush()
    db.add(Repository(project_id=project.id, url=synthetic_repo, provider="local"))
    db.commit()

    run = AnalysisRun(project_id=project.id, status="pending", stage_status={})
    db.add(run)
    db.commit()
    db.refresh(run)

    # Request cancellation before the pipeline even starts.
    run.cancel_requested = True
    db.add(run)
    db.commit()

    result = run_analysis(db, project, run=run)
    assert result.status == "cancelled"

    # A cancelled run must never be surfaced as the project's "latest complete" analysis.
    from app.services.query_service import get_latest_complete_run

    assert get_latest_complete_run(db, project.id) is None
