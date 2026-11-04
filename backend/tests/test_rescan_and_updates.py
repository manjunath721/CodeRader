import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import Base, get_db
import app.core.db as db_module
from app.main import app
from app.models.analysis import AnalysisRun, ResilienceScore, RiskScore
from app.models.developer import Developer, DeveloperAlias
from app.models.project import Project, Repository


@pytest.fixture
def api_client(synthetic_repo):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
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
    client = TestClient(app)
    yield client, TestSession
    app.dependency_overrides.clear()


def test_health_probes(api_client):
    client, _ = api_client
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.get("/api/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"

    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["database"] == "connected"


def test_risk_configuration_endpoint_and_propagation(api_client, synthetic_repo):
    client, _ = api_client
    # Create project
    r = client.post("/api/projects", json={"name": "Risk Config Test"})
    assert r.status_code == 201
    proj_id = r.json()["id"]

    # Get risk config
    r = client.get(f"/api/projects/{proj_id}/risk-config")
    assert r.status_code == 200
    cfg = r.json()
    assert "risk_weights" in cfg
    assert "knowledge_weights" in cfg

    # Update risk config
    custom_weights = {
        "knowledge_concentration": 0.50,
        "bus_factor_risk": 0.20,
        "documentation_risk": 0.10,
        "complexity_risk": 0.10,
        "change_frequency_risk": 0.05,
        "dependency_risk": 0.05,
    }
    r = client.patch(
        f"/api/projects/{proj_id}/risk-config",
        json={"risk_weights": custom_weights, "bus_factor_threshold": 5},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["risk_weights"]["knowledge_concentration"] == 0.50
    assert updated["bus_factor_threshold"] == 5

    # Configure rescan schedule
    r = client.patch(f"/api/projects/{proj_id}/schedule?interval_hours=24")
    assert r.status_code == 200
    assert r.json()["rescan_interval_hours"] == 24


def test_rescan_modes_comparison_and_exports(api_client, synthetic_repo):
    client, _ = api_client

    # 1. Setup project and attach repo
    r = client.post("/api/projects", json={"name": "Rescan Test Project"})
    assert r.status_code == 201
    project = r.json()
    proj_id = project["id"]

    r = client.post(f"/api/projects/{proj_id}/repositories", json={"url": synthetic_repo, "provider": "local"})
    assert r.status_code == 201

    # 2. Initial Full Scan
    r = client.post(f"/api/projects/{proj_id}/analyze?scan_mode=full")
    assert r.status_code == 202
    run1_id = r.json()["id"]

    r = client.get(f"/api/projects/{proj_id}/analysis-runs/{run1_id}")
    assert r.status_code == 200
    run1_data = r.json()
    assert run1_data["status"] == "complete"
    assert run1_data["commit_sha"] is not None

    # 3. Incremental Rescan
    r = client.post(f"/api/projects/{proj_id}/analyze?scan_mode=incremental")
    assert r.status_code == 202
    run2_id = r.json()["id"]

    r = client.get(f"/api/projects/{proj_id}/analysis-runs/{run2_id}")
    assert r.status_code == 200
    run2_data = r.json()
    assert run2_data["status"] == "complete"

    # 4. Compare run 1 and run 2
    r = client.get(f"/api/projects/{proj_id}/analysis-runs/{run1_id}/compare/{run2_id}")
    assert r.status_code == 200
    comp = r.json()
    assert "resilience_delta" in comp
    assert "risk_changes" in comp
    assert comp["base_run_id"] == run1_id
    assert comp["target_run_id"] == run2_id

    # 5. Export JSON
    r = client.get(f"/api/projects/{proj_id}/analysis-runs/{run1_id}/export?format=json")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    exported = r.json()
    assert exported["project_id"] == proj_id
    assert "module_risks" in exported
    assert "knowledge_distribution" in exported
    assert "recommendations" in exported

    # 6. Export CSV
    r = client.get(f"/api/projects/{proj_id}/analysis-runs/{run1_id}/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "module_name,risk_score" in r.text


def test_simulation_developer_membership_validation(api_client, synthetic_repo):
    client, _ = api_client
    r = client.post("/api/projects", json={"name": "Sim Validation Project"})
    proj_id = r.json()["id"]

    # Random fake developer ID that does not belong to project
    fake_dev_id = str(uuid.uuid4())
    r = client.post(
        "/api/simulations/developer-unavailability",
        json={"project_id": proj_id, "developer_id": fake_dev_id},
    )
    # Must fail with 400 Bad Request
    assert r.status_code == 400
    assert "do not belong to project" in r.json()["detail"]


def test_developer_alias_management(api_client):
    client, TestSession = api_client
    db = TestSession()
    proj = Project(name="Alias Test Proj")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    dev = Developer(project_id=proj.id, display_name="Jane Doe", primary_email="jane@corp.com", normalized_key="janedoe")
    db.add(dev)
    db.commit()
    db.refresh(dev)

    alias = DeveloperAlias(developer_id=dev.id, raw_name="Jane D", raw_email="j@corp.com", confidence="suggested", confirmed=False)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    dev_id = dev.id
    alias_id = alias.id
    db.close()

    r = client.get(f"/api/developers/{dev_id}/aliases")
    assert r.status_code == 200
    aliases = r.json()
    assert len(aliases) == 1
    assert aliases[0]["raw_name"] == "Jane D"
    assert aliases[0]["confirmed"] is False

    r = client.post(f"/api/developers/{dev_id}/aliases/{alias_id}/confirm")
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"
