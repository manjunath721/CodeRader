from pathlib import Path

from app.models.activity import Commit
from app.models.code import File as FileModel
from app.models.code import Module, ModuleDependency
from app.models.developer import Developer
from app.models.project import Project, Repository
from app.services.ingestion_service import ingest_repository


def test_ingest_repository_extracts_developers_modules_files_commits(db_session, synthetic_repo):
    project = Project(name="Test")
    db_session.add(project)
    db_session.flush()
    repo_row = Repository(project_id=project.id, url=synthetic_repo, provider="local")
    db_session.add(repo_row)
    db_session.flush()

    summary = ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)

    assert summary["developers"] == 4
    assert summary["modules"] == 2
    assert summary["files_total"] == 2
    assert summary["commits_inserted"] == 13
    assert summary["commits_fetched"] == 13
    assert summary["incremental"] is False  # first run, nothing to resume from

    modules = {m.name for m in db_session.query(Module).all()}
    assert modules == {"payment", "auth"}

    devs = {d.display_name for d in db_session.query(Developer).all()}
    assert devs == {"Rahul", "Priya", "Akash", "Bob"}

    assert db_session.query(Commit).count() == 13
    assert db_session.query(FileModel).count() == 2
    assert repo_row.commit_count == db_session.query(Commit).count()


def test_second_run_with_no_new_commits_is_a_fast_noop(db_session, synthetic_repo):
    """Incremental indexing: re-running against an unchanged repo should
    fetch and insert zero new commits, and should not duplicate any rows."""
    project = Project(name="Test")
    db_session.add(project)
    db_session.flush()
    repo_row = Repository(project_id=project.id, url=synthetic_repo, provider="local")
    db_session.add(repo_row)
    db_session.flush()

    ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    assert db_session.query(Commit).count() == 13
    assert db_session.query(Developer).count() == 4

    second = ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    assert second["incremental"] is True
    assert second["commits_fetched"] == 0
    assert second["commits_inserted"] == 0

    # No duplication of any previously-ingested rows.
    assert db_session.query(Commit).count() == 13
    assert db_session.query(Developer).count() == 4
    assert db_session.query(Module).count() == 2
    assert db_session.query(FileModel).count() == 2

    # All files were unchanged -> fully served from the content-hash cache.
    assert second["files_analyzed"] == 0
    assert second["files_cached"] == 2


def test_incremental_run_only_processes_new_commit(db_session, synthetic_repo):
    """Adding exactly one new commit after the first ingestion should result
    in exactly one new Commit row, not a full re-walk of history."""
    import os
    from git import Actor, Repo

    project = Project(name="Test")
    db_session.add(project)
    db_session.flush()
    repo_row = Repository(project_id=project.id, url=synthetic_repo, provider="local")
    db_session.add(repo_row)
    db_session.flush()

    ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    assert db_session.query(Commit).count() == 13

    git_repo = Repo(synthetic_repo)
    new_file = os.path.join(synthetic_repo, "src/payment/new_feature.py")
    with open(new_file, "w") as f:
        f.write("def new_feature():\n    return True\n")
    git_repo.index.add(["src/payment/new_feature.py"])
    git_repo.index.commit("add new feature", author=Actor("Rahul", "rahul@example.com"))

    second = ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    assert second["incremental"] is True
    assert second["commits_fetched"] == 1
    assert second["commits_inserted"] == 1
    assert db_session.query(Commit).count() == 14
    # The new file is analyzed; the two pre-existing unchanged files are cached.
    assert second["files_analyzed"] == 1
    assert second["files_cached"] == 2


def test_ingestion_is_idempotent_and_safe_to_retry(db_session, synthetic_repo):
    """Re-running ingest_repository against the SAME commit range twice
    (simulating a retry after a crash) must not duplicate Commit rows,
    thanks to the (repository_id, hash) unique constraint + pre-check."""
    project = Project(name="Test")
    db_session.add(project)
    db_session.flush()
    repo_row = Repository(project_id=project.id, url=synthetic_repo, provider="local")
    db_session.add(repo_row)
    db_session.flush()

    ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    # Simulate a crash-before-checkpoint-update by resetting the incremental
    # marker, forcing the same range to be fetched again.
    repo_row.last_indexed_commit_sha = None
    db_session.add(repo_row)
    db_session.commit()

    retry = ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    assert retry["commits_fetched"] == 13
    assert retry["commits_inserted"] == 0  # all 13 already present
    assert retry["commits_already_present"] == 13
    assert db_session.query(Commit).count() == 13  # no duplicates


def test_full_scan_backfills_history_omitted_by_quick_scan(db_session, synthetic_repo, monkeypatch):
    monkeypatch.setattr("app.services.ingestion_service.QUICK_SCAN_MAX_COMMITS", 5)
    project = Project(name="Quick-to-full")
    db_session.add(project)
    db_session.flush()
    repo_row = Repository(project_id=project.id, url=synthetic_repo, provider="local")
    db_session.add(repo_row)
    db_session.flush()

    quick = ingest_repository(db_session, repo_row, synthetic_repo, is_local=True, scan_mode="quick")
    assert quick["commits_inserted"] == 5
    assert db_session.query(Commit).count() == 5

    full = ingest_repository(db_session, repo_row, synthetic_repo, is_local=True, scan_mode="full")

    assert full["incremental"] is False
    assert full["commits_fetched"] == 13
    assert full["commits_inserted"] == 8
    assert db_session.query(Commit).count() == 13
    assert repo_row.scan_mode == "full"


def test_deleted_import_removes_only_stale_generated_dependency_edges(db_session, synthetic_repo):
    payment_file = Path(synthetic_repo) / "src/payment/charge.py"
    payment_file.write_text("import src.auth.login\n\ndef charge():\n    return True\n", encoding="utf-8")

    project = Project(name="Dependency reconciliation")
    db_session.add(project)
    db_session.flush()
    repo_row = Repository(project_id=project.id, url=synthetic_repo, provider="local")
    db_session.add(repo_row)
    db_session.flush()

    ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)
    modules = {module.path_prefix: module for module in db_session.query(Module).all()}
    assert db_session.query(ModuleDependency).filter_by(source="import").count() == 1

    db_session.add(
        ModuleDependency(
            module_id=modules["src/auth"].id,
            depends_on_module_id=modules["src/payment"].id,
            source="manual",
            weight=1.0,
        )
    )
    db_session.commit()
    payment_file.write_text("def charge():\n    return True\n", encoding="utf-8")

    ingest_repository(db_session, repo_row, synthetic_repo, is_local=True)

    edges = db_session.query(ModuleDependency).all()
    assert [(edge.source, edge.module_id, edge.depends_on_module_id) for edge in edges] == [
        ("manual", modules["src/auth"].id, modules["src/payment"].id)
    ]
