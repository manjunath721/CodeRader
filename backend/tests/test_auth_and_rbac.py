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
from app.models.auth import User, ProjectMember, AuditLog
from app.models.project import Project


@pytest.fixture
def auth_client():
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
    yield client
    app.dependency_overrides.clear()


def test_auth_registration_and_login_flow(auth_client):
    # Register first user (should automatically be admin)
    r = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "Password123!", "full_name": "Alice Architect"},
    )
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["role"] == "admin"
    token = data["access_token"]

    # Verify /auth/me with bearer token
    r = auth_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"

    # Login with valid credentials
    r = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Password123!"},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()

    # Login with invalid password
    r = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassword"},
    )
    assert r.status_code == 401


def test_rbac_project_access_and_audit_logging(auth_client):
    # Register owner
    r = auth_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "Password123!", "full_name": "Project Owner"},
    )
    assert r.status_code == 201
    owner_token = r.json()["access_token"]

    # Register second normal user
    r = auth_client.post(
        "/api/auth/register",
        json={"email": "viewer@example.com", "password": "Password123!", "full_name": "Team Viewer"},
    )
    assert r.status_code == 201
    viewer_token = r.json()["access_token"]

    # Register third unrelated user
    r = auth_client.post(
        "/api/auth/register",
        json={"email": "stranger@example.com", "password": "Password123!", "full_name": "Stranger"},
    )
    assert r.status_code == 201
    stranger_token = r.json()["access_token"]

    # Owner creates a project
    r = auth_client.post(
        "/api/projects",
        json={"name": "Secure Platform Project", "description": "Confidential repository analysis"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r.status_code == 201
    project = r.json()
    proj_id = project["id"]

    # Add viewer as a member
    r = auth_client.post(
        f"/api/projects/{proj_id}/members",
        json={"email": "viewer@example.com", "role": "viewer"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert r.status_code == 201

    # Viewer can read the project
    r = auth_client.get(f"/api/projects/{proj_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "Secure Platform Project"

    # Stranger cannot read the project (403 Forbidden)
    r = auth_client.get(f"/api/projects/{proj_id}", headers={"Authorization": f"Bearer {stranger_token}"})
    assert r.status_code == 403

    # Viewer cannot delete project (only owner can)
    r = auth_client.delete(f"/api/projects/{proj_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 403

    # Check audit logs for the project
    r = auth_client.get(f"/api/projects/{proj_id}/audit-logs", headers={"Authorization": f"Bearer {owner_token}"})
    assert r.status_code == 200
    logs = r.json()
    assert len(logs) >= 2
    actions = [l["action"] for l in logs]
    assert "PROJECT_CREATED" in actions
    assert "MEMBER_ADDED" in actions
