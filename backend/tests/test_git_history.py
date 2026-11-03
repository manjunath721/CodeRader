from git import Repo

from app.analyzers.git_history import (
    commit_exists,
    extract_commit_history,
    get_current_branch,
    get_head_commit_sha,
)


def test_cli_extraction_matches_gitpython_exactly(synthetic_repo):
    records = extract_commit_history(synthetic_repo)
    git_repo = Repo(synthetic_repo)
    gp_commits = list(git_repo.iter_commits())

    assert len(records) == len(gp_commits)
    assert {r.hash for r in records} == {c.hexsha for c in gp_commits}

    by_hash = {r.hash: r for r in records}
    for c in gp_commits:
        cli_total = sum(f.insertions + f.deletions for f in by_hash[c.hexsha].files)
        gp_total = sum(v["insertions"] + v["deletions"] for v in c.stats.files.values())
        assert cli_total == gp_total


def test_incremental_range_excludes_checkpoint_commit(synthetic_repo):
    git_repo = Repo(synthetic_repo)
    all_commits = list(git_repo.iter_commits())
    checkpoint = all_commits[5].hexsha

    records = extract_commit_history(synthetic_repo, since_commit_sha=checkpoint)
    assert checkpoint not in {r.hash for r in records}
    assert len(records) == 5  # commits strictly after the checkpoint


def test_max_commits_bounds_history_depth(synthetic_repo):
    records = extract_commit_history(synthetic_repo, max_commits=3)
    assert len(records) == 3


def test_commit_exists_true_for_real_sha_false_for_fake(synthetic_repo):
    git_repo = Repo(synthetic_repo)
    real_sha = next(git_repo.iter_commits()).hexsha
    assert commit_exists(synthetic_repo, real_sha) is True
    assert commit_exists(synthetic_repo, "f" * 40) is False


def test_head_and_branch_helpers(synthetic_repo):
    assert get_head_commit_sha(synthetic_repo) is not None
    assert get_current_branch(synthetic_repo)  # non-empty string
