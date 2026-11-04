import pytest

from app.models.analysis import AnalysisRun, ResilienceScore, RiskScore
from app.models.code import Module
from app.models.project import Project, Repository
from app.models.simulation import Recommendation
from app.services.analysis_pipeline import run_analysis


def test_full_pipeline_runs_and_scores_concentrated_module_higher(db_session, synthetic_repo):
    project = Project(name="Demo")
    db_session.add(project)
    db_session.flush()
    db_session.add(Repository(project_id=project.id, url=synthetic_repo, provider="local"))
    db_session.commit()

    run = run_analysis(db_session, project)
    assert run.status == "complete"
    assert set(run.stage_status.values()) == {"complete"}

    risk_by_name = {}
    for m in db_session.query(Module).all():
        rs = db_session.query(RiskScore).filter_by(module_id=m.id).first()
        risk_by_name[m.name] = rs

    # payment's concentrated ownership (Rahul dominant) should score higher risk
    # and a lower bus factor than auth's evenly-spread ownership.
    assert risk_by_name["payment"].concentration_pct > risk_by_name["auth"].concentration_pct
    assert risk_by_name["payment"].bus_factor <= risk_by_name["auth"].bus_factor

    resilience = db_session.query(ResilienceScore).filter_by(project_id=project.id).first()
    assert resilience is not None
    assert 0 <= resilience.score <= 100

    recommendations = db_session.query(Recommendation).filter_by(project_id=project.id).all()
    assert isinstance(recommendations, list)  # may be empty depending on thresholds, but must not error


def test_failed_analysis_does_not_persist_exception_details(db_session, monkeypatch):
    project = Project(name="Failure case")
    db_session.add(project)
    db_session.flush()
    db_session.add(Repository(project_id=project.id, url="/repo", provider="local"))
    db_session.commit()

    def fail_with_sensitive_details(*_args, **_kwargs):
        raise RuntimeError("database password at C:/private/secrets.env")

    monkeypatch.setattr("app.services.analysis_pipeline.ingest_repository", fail_with_sensitive_details)

    with pytest.raises(RuntimeError):
        run_analysis(db_session, project)

    failed_run = db_session.query(AnalysisRun).one()
    assert failed_run.status == "failed"
    assert failed_run.error_message == "Analysis failed. Please retry or contact support."
    assert "private/secrets.env" not in failed_run.error_message
