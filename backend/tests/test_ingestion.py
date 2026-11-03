from app.models.activity import Commit
from app.models.code import File as FileModel
from app.models.code import Module
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
