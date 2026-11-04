import pytest

from app.analyzers import git_clone
from app.core.errors import InvalidGitURLError


@pytest.mark.parametrize("resolved_ips", [["8.8.8.8", "127.0.0.1"], []])
def test_repo_url_rejects_mixed_or_empty_dns_resolution(monkeypatch, resolved_ips):
    monkeypatch.setattr(git_clone.settings, "ALLOW_PRIVATE_NETWORK_REPOS", False)
    monkeypatch.setattr(git_clone, "_resolve_host_ips", lambda _host: resolved_ips)

    with pytest.raises(InvalidGitURLError):
        git_clone.validate_repo_url("https://example.test/owner/repository.git")


def test_repo_url_allows_only_public_dns_answers(monkeypatch):
    monkeypatch.setattr(git_clone.settings, "ALLOW_PRIVATE_NETWORK_REPOS", False)
    monkeypatch.setattr(git_clone, "_resolve_host_ips", lambda _host: ["8.8.8.8", "1.1.1.1"])

    assert git_clone.validate_repo_url("https://example.test/owner/repository.git") == (
        "https://example.test/owner/repository.git"
    )
