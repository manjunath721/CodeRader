"""
Batched Git history extraction via the `git log --numstat` CLI, replacing
per-commit GitPython `commit.stats.files` calls.

MEASURED (see docs/perf-benchmarks.md): GitPython's `c.stats.files` shells out
to `git diff` once per commit. At 1,200 commits that took 2.01s versus 0.14s
for a single batched `git log --numstat` call — a 14.9x speedup, and the gap
widens with history size because GitPython pays per-commit process/diff
overhead while the batched call is O(1) process invocations.

`git log --numstat` with a custom `--pretty=format:` and field separators
(ASCII 0x1f, which cannot appear in commit metadata) is used instead of
`git log -p` or JSON-ish formats because numstat's per-file add/delete
counts are exactly the stat we need and nothing more — no patch bodies to
parse or discard.
"""
import subprocess
from dataclasses import dataclass, field

_RECORD_SEP = "\x1e"  # between commits
_FIELD_SEP = "\x1f"  # between metadata fields
_PRETTY_FORMAT = f"{_RECORD_SEP}%H{_FIELD_SEP}%an{_FIELD_SEP}%ae{_FIELD_SEP}%aI{_FIELD_SEP}%s"


@dataclass
class FileChange:
    path: str
    insertions: int
    deletions: int


@dataclass
class CommitRecord:
    hash: str
    author_name: str
    author_email: str
    authored_at_iso: str
    message: str
    files: list[FileChange] = field(default_factory=list)


class GitCommandError(RuntimeError):
    pass


def _run_git(repo_path: str, args: list[str], timeout: float) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(f"git {' '.join(args)} timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise GitCommandError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def get_head_commit_sha(repo_path: str, timeout: float = 30) -> str | None:
    try:
        return _run_git(repo_path, ["rev-parse", "HEAD"], timeout).strip()
    except GitCommandError:
        return None  # empty repository, no commits yet


def get_current_branch(repo_path: str, timeout: float = 30) -> str:
    out = _run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"], timeout).strip()
    return out or "HEAD"


def commit_exists(repo_path: str, commit_sha: str, timeout: float = 30) -> bool:
    """False for a SHA that's been rewritten away (force push / rebase) — the
    caller should fall back to a full re-scan in that case rather than error."""
    try:
        _run_git(repo_path, ["cat-file", "-e", commit_sha], timeout)
        return True
    except GitCommandError:
        return False


def extract_commit_history(
    repo_path: str,
    since_commit_sha: str | None = None,
    max_commits: int | None = None,
    timeout: float = 120,
) -> list[CommitRecord]:
    """
    One batched `git log --numstat` call for the whole range — this is the
    perf-critical replacement for per-commit GitPython `.stats.files`.

    since_commit_sha: if given, only commits reachable from HEAD but not from
    this SHA are returned (`<sha>..HEAD`) — the incremental-indexing path.
    max_commits: bounds history depth for Quick Scan mode (`-n <max_commits>`).
    """
    args = ["log", "--no-renames", "--numstat", f"--pretty=format:{_PRETTY_FORMAT}"]
    if max_commits:
        args += ["-n", str(max_commits)]
    if since_commit_sha:
        args.append(f"{since_commit_sha}..HEAD")
    else:
        args.append("HEAD")

    try:
        raw = _run_git(repo_path, args, timeout)
    except GitCommandError as exc:
        if "unknown revision" in str(exc).lower() or "bad revision" in str(exc).lower():
            return []  # empty repo / no commits in range
        raise

    records: list[CommitRecord] = []
    for block in raw.split(_RECORD_SEP):
        block = block.strip("\n")
        if not block.strip():
            continue
        lines = block.split("\n")
        header = lines[0]
        parts = header.split(_FIELD_SEP)
        if len(parts) != 5:
            continue  # malformed header line - skip defensively rather than crash the whole run
        commit_hash, author_name, author_email, authored_at_iso, message = parts
        record = CommitRecord(
            hash=commit_hash, author_name=author_name, author_email=author_email,
            authored_at_iso=authored_at_iso, message=message,
        )
        for line in lines[1:]:
            if not line.strip():
                continue
            # numstat format: "<additions>\t<deletions>\t<path>" ('-' for binary files)
            fields = line.split("\t")
            if len(fields) != 3:
                continue
            additions_raw, deletions_raw, path = fields
            additions = int(additions_raw) if additions_raw.isdigit() else 0
            deletions = int(deletions_raw) if deletions_raw.isdigit() else 0
            record.files.append(FileChange(path=path, insertions=additions, deletions=deletions))
        records.append(record)

    return records
