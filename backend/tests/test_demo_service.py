from app.models.developer import Developer
from app.models.code import Module, ModuleDependency
from app.models.project import Project
from app.services.demo_service import ensure_demo_project


def test_ensure_demo_builds_expected_workspace(db_session):
    result = ensure_demo_project(db_session)
    assert result["status"] == "complete"
    assert result["created"] is True

    project = db_session.get(Project, result["project_id"])
    assert project is not None
    assert project.is_demo is True

    dev_names = {d.display_name for d in db_session.query(Developer).filter_by(project_id=project.id)}
    assert len(dev_names) == 10
    assert {"Rahul", "Priya", "Vikram", "Meera"} <= dev_names

    module_names = {m.name for m in db_session.query(Module).all()}
    assert {"payment", "billing", "checkout", "auth", "notifications", "reporting", "search", "deployment"} <= module_names

    # Mixed dependency graph: real auto-detected edges, including the diamond.
    assert db_session.query(ModuleDependency).count() >= 5


def test_ensure_demo_is_idempotent(db_session):
    first = ensure_demo_project(db_session)
    assert first["status"] == "complete"
    second = ensure_demo_project(db_session)
    assert second["created"] is False
    assert second["project_id"] == first["project_id"]
    assert second["status"] == "complete"
    assert db_session.query(Project).filter_by(is_demo=True).count() == 1
