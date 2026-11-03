from app.risk.risk_engine import (
    ModuleRiskInput,
    ResilienceInput,
    compute_criticality,
    compute_module_risks,
    compute_resilience_score,
    resilience_label,
    risk_level,
)


def test_risk_levels_boundaries():
    assert risk_level(10) == "LOW"
    assert risk_level(30) == "MODERATE"
    assert risk_level(60) == "HIGH"
    assert risk_level(90) == "CRITICAL"


def test_high_concentration_low_bus_factor_yields_high_risk():
    inputs = [
        ModuleRiskInput(
            module_id="payment", concentration_pct=88, bus_factor=1, documentation_score=0.25,
            complexity_avg=20, change_frequency_90d=40, dependency_centrality=2,
        ),
        ModuleRiskInput(
            module_id="auth", concentration_pct=25, bus_factor=4, documentation_score=0.8,
            complexity_avg=5, change_frequency_90d=5, dependency_centrality=0,
        ),
    ]
    results = {r.module_id: r for r in compute_module_risks(inputs)}
    assert results["payment"].score > results["auth"].score
    assert results["payment"].level in ("HIGH", "CRITICAL")
    assert "values" in results["payment"].factors and "weights" in results["payment"].factors


def test_criticality_requires_both_risk_and_structural_importance():
    crit_score, is_critical = compute_criticality(
        risk_score=90, dependency_centrality_norm=1.0, change_frequency_norm=1.0, loc_share=1.0
    )
    assert crit_score == 90.0
    assert is_critical is True

    low_importance_score, not_critical = compute_criticality(
        risk_score=90, dependency_centrality_norm=0.0, change_frequency_norm=0.0, loc_share=0.0
    )
    assert low_importance_score == 0.0
    assert not_critical is False


def test_resilience_score_and_label():
    score, label, breakdown = compute_resilience_score(
        ResilienceInput(
            avg_bus_factor_norm=0.8, avg_knowledge_distribution=0.7, avg_documentation_coverage=0.6,
            avg_critical_module_risk=20, dependency_concentration=0.2,
        )
    )
    assert 0 <= score <= 100
    assert resilience_label(score) in ("GOOD", "MODERATE", "AT_RISK", "CRITICAL")
    assert "components" in breakdown
