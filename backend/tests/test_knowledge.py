from datetime import datetime, timezone

from app.risk.knowledge import ModuleActivity, bus_factor, compute_module_knowledge_scores, knowledge_concentration_hhi


def test_knowledge_scores_favor_higher_contribution_and_recency():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    activity = {
        "dev_a": ModuleActivity(commits_count=20, lines_changed=500, last_commit_at=datetime(2026, 5, 20, tzinfo=timezone.utc)),
        "dev_b": ModuleActivity(commits_count=2, lines_changed=10, last_commit_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
    }
    results = {r.developer_id: r.score for r in compute_module_knowledge_scores("mod1", activity, now=now)}
    assert results["dev_a"] > results["dev_b"]
    assert 0 <= results["dev_b"] <= 100


def test_single_contributor_gets_full_score():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    activity = {"solo": ModuleActivity(commits_count=5, lines_changed=100, last_commit_at=now)}
    results = compute_module_knowledge_scores("mod1", activity, now=now)
    assert results[0].score == 100.0


def test_hhi_concentration_single_owner_is_maximal():
    assert knowledge_concentration_hhi([100.0]) == 100.0


def test_hhi_concentration_even_split_is_low():
    # 5-way even split -> HHI = 5*(20^2) = 2000 -> /100 = 20
    result = knowledge_concentration_hhi([20.0] * 5)
    assert result == 20.0


def test_bus_factor_counts_meaningful_contributors():
    scores = {"a": 82, "b": 13, "c": 5}
    assert bus_factor(scores, threshold=10) == 2
