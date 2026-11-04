"""
Repository acquisition: URL validation, SSRF protection, and bounded cloning
with Quick Scan / Full Historical Scan modes (master spec §35, §6, and the
perf-hardening pass).

Uses the `git` CLI directly via subprocess rather than GitPython's
`Repo.clone_from` so we get real control over timeouts, shallow-clone depth,
and can enforce size/file-count budgets immediately after the clone
completes and before any analysis work starts.
"""
import ipaddress
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.errors import CodeResilienceError, InvalidGitURLError, RepositoryNotAccessibleError

settings = get_settings()

# Quick Scan: bounded-depth clone + a hard cap on commits processed, for a fast
# first look at a large repository. Full Historical Scan: complete history.
QUICK_SCAN_CLONE_DEPTH = 500
QUICK_SCAN_MAX_COMMITS = 500


class RepositoryBudgetExceededError(CodeResilienceError):
    code = "REPOSITORY_BUDGET_EXCEEDED"
    status_code = 422
    message = "Repository exceeds the configured size or file-count budget."


def _resolve_host_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return []
    return list({info[4][0] for info in infos})


def _is_private_or_local(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # can't parse -> treat as unsafe
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast


def validate_repo_url(url: str) -> str:
    """
    Raises InvalidGitURLError for a disallowed scheme/host, or one that
    resolves to a private/loopback/link-local address — blocks SSRF against
    internal infrastructure via a crafted repository URL. Set
    ALLOW_PRIVATE_NETWORK_REPOS=true (e.g. for an on-prem GitHub Enterprise)
    to opt out of the private-IP check for trusted deployments.
    """
    parsed = urlparse(url)
    if parsed.scheme not in settings.ALLOWED_REPO_SCHEMES:
        raise InvalidGitURLError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.netloc and parsed.scheme != "git":
        raise InvalidGitURLError("Repository URL is missing a host.")

    if not settings.ALLOW_PRIVATE_NETWORK_REPOS and parsed.hostname:
        if parsed.hostname in ("localhost",):
            raise InvalidGitURLError("Repository URL resolves to a local/private address.")
        ips = _resolve_host_ips(parsed.hostname)
        if not ips or any(_is_private_or_local(ip) for ip in ips):
            raise InvalidGitURLError("Repository URL resolves to a local/private address or has no DNS records.")
    return url


def _dir_size_and_count(path: str) -> tuple[int, int]:
    total_bytes = 0
    total_files = 0
    for p in Path(path).rglob("*"):
        if p.is_file():
            total_bytes += p.stat().st_size
            total_files += 1
    return total_bytes, total_files


def clone_repository(
    url: str,
    local_path: str | None = None,
    scan_mode: str = "full",
) -> str:
    """
    Clones `url` to a scratch directory (or returns `local_path` unchanged
    for already-local test/demo repos) and returns the working directory
    path. Caller is responsible for cleanup via `cleanup_clone`.

    scan_mode="quick" performs a shallow, bounded-depth clone
    (QUICK_SCAN_CLONE_DEPTH) for a fast first look; "full" clones complete
    history. Either way, a hard wall-clock timeout and a post-clone
    disk-size/file-count budget are enforced before any analysis begins.
    """
    if local_path:
        if not Path(local_path).exists():
            raise RepositoryNotAccessibleError(f"Local repository path does not exist: {local_path}")
        return local_path

    validate_repo_url(url)
    dest = tempfile.mkdtemp(prefix="coderesilience_clone_")
    # Hardened git invocation:
    # 1. core.hooksPath=/dev/null prevents execution of malicious repository hooks
    # 2. protocol.file.allow=never blocks submodule local file inclusion exploits
    args = [
        "git",
        "-c", "core.hooksPath=/dev/null",
        "-c", "protocol.file.allow=never",
        "clone",
        "--no-single-branch",
    ]
    if scan_mode == "quick":
        args += ["--depth", str(QUICK_SCAN_CLONE_DEPTH)]
    args += [url, dest]

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=settings.CLONE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepositoryNotAccessibleError(
            f"Clone timed out after {settings.CLONE_TIMEOUT_SECONDS}s."
        ) from exc

    if result.returncode != 0:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepositoryNotAccessibleError(f"Could not clone repository: {result.stderr.strip()}")

    total_bytes, total_files = _dir_size_and_count(dest)
    size_mb = total_bytes / (1024 * 1024)
    if size_mb > settings.MAX_REPO_SIZE_MB:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepositoryBudgetExceededError(
            f"Repository is {size_mb:.0f} MB, exceeding the {settings.MAX_REPO_SIZE_MB} MB budget. "
            f"Try Quick Scan mode, or raise MAX_REPO_SIZE_MB."
        )
    if total_files > settings.MAX_REPO_FILE_COUNT:
        shutil.rmtree(dest, ignore_errors=True)
        raise RepositoryBudgetExceededError(
            f"Repository has {total_files} files, exceeding the {settings.MAX_REPO_FILE_COUNT} file budget."
        )
    return dest


def cleanup_clone(path: str, was_local: bool) -> None:
    if not was_local:
        shutil.rmtree(path, ignore_errors=True)
