from app.recommendations.engine import (
    generate_knowledge_transfer_plan,
    generate_recommendations,
)


def test_rule_based_recommendations_coverage():
    module_risks = [
        {
            "module_id": "mod-1",
            "name": "payment_service",
            "score": 85.0,
            "level": "CRITICAL",
            "bus_factor": 1,
            "documentation_score": 0.25,
            "concentration_pct": 88.0,
            "complexity_avg": 18.5,
            "change_frequency_90d": 65,
            "dependency_centrality": 5.0,
        },
        {
            "module_id": "mod-2",
            "name": "user_auth",
            "score": 35.0,
            "level": "MODERATE",
            "bus_factor": 3,
            "documentation_score": 0.85,
            "concentration_pct": 40.0,
            "complexity_avg": 8.0,
            "change_frequency_90d": 12,
            "dependency_centrality": 2.0,
        },
    ]

    drift_flags = [
        {"module_id": "mod-1", "name": "payment_service", "message": "Knowledge concentration grew by 15%"}
    ]
    critical_areas = [{"module_id": "mod-1", "name": "payment_service"}]

    recs = generate_recommendations(module_risks, drift_flags, critical_areas)
    assert len(recs) >= 5

    rule_types = {r.rule_type for r in recs}
    assert "LOW_BUS_FACTOR" in rule_types
    assert "HIGH_KNOWLEDGE_CONCENTRATION" in rule_types
    assert "LOW_DOCUMENTATION" in rule_types
    assert "HIGH_COMPLEXITY" in rule_types
    assert "HIGH_CHURN" in rule_types
    assert "HIGH_CENTRALITY" in rule_types
    assert "DRIFT_INCREASING" in rule_types

    # Ensure all recommendations have actionable fields
    for r in recs:
        assert r.severity in ("CRITICAL", "HIGH", "MODERATE", "LOW")
        assert len(r.title) > 0
        assert len(r.description) > 0
        assert r.suggested_action is not None
        assert r.triggering_metric is not None


def test_knowledge_transfer_plan_generation():
    plan = generate_knowledge_transfer_plan(
        module_name="billing_engine",
        backup_developer_id="dev-456",
        priority="HIGH",
    )
    assert plan["module"] == "billing_engine"
    assert plan["recommended_backup_developer_id"] == "dev-456"
    assert plan["priority"] == "HIGH"
    assert len(plan["topics"]) >= 5
    assert any("architectural design" in t for t in plan["topics"])
