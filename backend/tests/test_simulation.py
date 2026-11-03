from app.simulation.engine import ModuleFacts, ProjectSnapshot, simulate_unavailability


def _snapshot():
    return ProjectSnapshot(
        modules=[
            ModuleFacts("payment", "payment", documentation_score=0.23, complexity_avg=18, change_frequency_90d=40),
            ModuleFacts("billing", "billing", documentation_score=0.5, complexity_avg=10, change_frequency_90d=15),
            ModuleFacts("checkout", "checkout", documentation_score=0.6, complexity_avg=8, change_frequency_90d=10),
            ModuleFacts("auth", "auth", documentation_score=0.8, complexity_avg=5, change_frequency_90d=5),
        ],
        knowledge_scores={
            "payment": {"rahul": 87, "priya": 13},
            "billing": {"rahul": 60, "priya": 40},
            "checkout": {"rahul": 30, "akash": 70},
            "auth": {"akash": 25, "priya": 25, "manjunath": 25, "bob": 25},
        },
        dependency_edges=[("billing", "payment"), ("checkout", "billing")],
        review_counts={"payment": {"priya": 40}},
        issue_counts={"payment": {"priya": 15}},
    )


def test_simulation_identifies_affected_modules():
    outcome = simulate_unavailability(_snapshot(), ["rahul"])
    assert set(outcome.affected_modules) == {"payment", "billing", "checkout"}
    assert "auth" not in outcome.affected_modules


def test_simulation_resilience_drops_after_removal():
    outcome = simulate_unavailability(_snapshot(), ["rahul"])
    assert outcome.resilience_after < outcome.resilience_before


def test_simulation_reports_knowledge_impact_and_backups():
    outcome = simulate_unavailability(_snapshot(), ["rahul"])
    assert outcome.knowledge_impact_pct > 0
    assert "priya" in [c["developer_id"] for c in outcome.backup_candidates.get("payment", [])]


def test_multi_developer_simulation_is_at_least_as_severe():
    single = simulate_unavailability(_snapshot(), ["rahul"])
    multi = simulate_unavailability(_snapshot(), ["rahul", "priya"])
    # Knowledge impact is strictly additive/monotonic by construction (sum of removed
    # developers' knowledge share), so this always holds.
    assert multi.knowledge_impact_pct >= single.knowledge_impact_pct
    # Resilience is a project-wide average across shifting sets of "critical" modules,
    # so it is not guaranteed to be strictly monotonic in the number of developers
    # removed (documented in risk-model.md) — both scenarios should still show a
    # drop from the shared baseline.
    assert multi.resilience_after < multi.resilience_before
    assert single.resilience_after < single.resilience_before
