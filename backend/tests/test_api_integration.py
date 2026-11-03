from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.core.db import Base, get_db
from app.main import app


from sqlalchemy.pool import StaticPool


def _make_client(synthetic_repo):
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
    # The analyze endpoint's background task opens its own session directly via
    # app.core.db.SessionLocal (by design — background tasks aren't request-scoped),
    # so route it to the same test database.
    import app.core.db as db_module

    db_module.SessionLocal = TestSession
    return TestClient(app)


def test_full_api_flow(synthetic_repo):
    client = _make_client(synthetic_repo)

    # Create project
    r = client.post("/api/projects", json={"name": "Demo Project"})
    assert r.status_code == 201
    project = r.json()

    # Attach local repository
    r = client.post(f"/api/projects/{project['id']}/repositories", json={"url": synthetic_repo, "provider": "local"})
    assert r.status_code == 201

    # Dashboard before analysis: no crash, empty resilience
    r = client.get(f"/api/projects/{project['id']}/dashboard")
    assert r.status_code == 200
    assert r.json()["resilience_score"] is None

    # Trigger analysis (BackgroundTasks run synchronously within TestClient's request handling)
    r = client.post(f"/api/projects/{project['id']}/analyze")
    assert r.status_code == 202
    run_id = r.json()["id"]

    r = client.get(f"/api/projects/{project['id']}/analysis-runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "complete"
    assert "ingestion" in r.json()["progress"]

    r = client.get(f"/api/projects/{project['id']}/analysis-runs")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Re-running analysis now exercises the incremental path with no new commits.
    r = client.post(f"/api/projects/{project['id']}/analyze")
    assert r.status_code == 202
    run2_id = r.json()["id"]
    r = client.get(f"/api/projects/{project['id']}/analysis-runs/{run2_id}")
    assert r.json()["status"] == "complete"
    second_ingestion = list(r.json()["progress"]["ingestion"].values())[0]
    assert second_ingestion["incremental"] is True
    assert second_ingestion["commits_inserted"] == 0

    # Dashboard after analysis
    r = client.get(f"/api/projects/{project['id']}/dashboard")
    dashboard = r.json()
    assert dashboard["resilience_score"] is not None
    assert dashboard["module_count"] == 2
    assert dashboard["developer_count"] == 4

    # Modules list + module detail
    r = client.get(f"/api/projects/{project['id']}/modules")
    modules = r.json()
    assert len(modules) == 2
    payment = next(m for m in modules if m["name"] == "payment")

    r = client.get(f"/api/modules/{payment['id']}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["knowledge_distribution"]
    rahul = next(k for k in detail["knowledge_distribution"] if k["developer_name"] == "Rahul")
    assert rahul["score"] > 0

    # Developers list + developer detail
    r = client.get(f"/api/projects/{project['id']}/developers")
    devs = r.json()
    rahul_dev = next(d for d in devs if d["display_name"] == "Rahul")
    r = client.get(f"/api/developers/{rahul_dev['id']}")
    assert r.status_code == 200

    # Knowledge graph
    r = client.get(f"/api/projects/{project['id']}/knowledge-graph")
    graph = r.json()
    assert len(graph["nodes"]) > 0

    # Risks + resilience
    r = client.get(f"/api/projects/{project['id']}/risks")
    assert len(r.json()) == 2
    r = client.get(f"/api/projects/{project['id']}/resilience")
    assert r.json()["score"] is not None

    # Simulation
    r = client.post(
        "/api/simulations/developer-unavailability",
        json={"project_id": project["id"], "developer_id": rahul_dev["id"]},
    )
    assert r.status_code == 200
    sim = r.json()
    assert sim["resilience_after"] < sim["resilience_before"]

    # Recommendations
    r = client.get(f"/api/projects/{project['id']}/recommendations")
    assert r.status_code == 200

    # AI analyst — grounded answer about the payment module
    r = client.post("/api/ai/query", json={"project_id": project["id"], "question": "Why is payment risky?"})
    assert r.status_code == 200
    ai_resp = r.json()
    assert "payment" in ai_resp["answer"].lower()
    assert ai_resp["context"]["type"] == "module_risk"

    # Cosmos layers — real per-file inventory + derived external libraries
    r = client.get(f"/api/projects/{project['id']}/files")
    assert r.status_code == 200
    files = r.json()
    assert len(files) == 2
    by_path = {f["path"]: f for f in files}
    assert by_path["src/payment/charge.py"]["module_name"] == "payment"
    assert by_path["src/auth/login.py"]["module_name"] == "auth"

    r = client.get(f"/api/projects/{project['id']}/libraries")
    assert r.status_code == 200
    assert isinstance(r.json(), list)  # synthetic repo captures no external imports

    # Delete project — full cascade, nothing orphaned
    r = client.delete(f"/api/projects/{project['id']}")
    assert r.status_code == 204
    r = client.get(f"/api/projects/{project['id']}")
    assert r.status_code == 404
    r = client.get(f"/api/projects/{project['id']}/dashboard")
    assert r.status_code == 404
    r = client.get("/api/projects")
    assert all(p["id"] != project["id"] for p in r.json())
    r = client.delete(f"/api/projects/{project['id']}")
    assert r.status_code == 404

    app.dependency_overrides.clear()
