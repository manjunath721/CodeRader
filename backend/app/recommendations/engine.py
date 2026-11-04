"""
Recommendation engine — deterministic, explainable, rule-based recommendations.
Consumes computed metrics (risk, bus factor, concentration, complexity, churn, centrality, documentation)
and generates prioritized action items with explicit triggering metrics, reasons, and suggested actions.
"""
from dataclasses import dataclass, field


@dataclass
class Recommendation:
    severity: str  # CRITICAL | HIGH | MODERATE | LOW
    title: str
    description: str
    module_id: str | None = None
    related_developer_id: str | None = None
    rule_type: str | None = None
    triggering_metric: str | None = None
    suggested_action: str | None = None


def generate_recommendations(
    module_risks: list[dict],
    drift_flags: list[dict] | None = None,
    critical_areas: list[dict] | None = None,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    drift_flags = drift_flags or []
    critical_areas = critical_areas or []

    for m in module_risks:
        mid = m.get("module_id")
        name = m.get("name", "Module")
        score = m.get("score", 0.0)
        level = m.get("level", "LOW")
        bus_factor = m.get("bus_factor", 1)
        doc_score = m.get("documentation_score", 1.0)
        concentration = m.get("concentration_pct", 0.0)
        complexity = m.get("complexity_avg", 0.0)
        change_freq = m.get("change_frequency_90d", 0)
        centrality = m.get("dependency_centrality", 0.0)

        # 1. Bus Factor <= 1 on High/Critical Risk Module
        if bus_factor <= 1 and level in ("HIGH", "CRITICAL"):
            recs.append(
                Recommendation(
                    severity="CRITICAL",
                    title=f"Low Bus Factor on {name} (BF={bus_factor})",
                    description=(
                        f"Module '{name}' relies almost exclusively on a single primary contributor. "
                        f"Triggering metric: Bus factor is {bus_factor} with overall risk score {score}/100. "
                        f"Suggested action: Identify and pair a secondary engineer to shadow commits and cross-train."
                    ),
                    module_id=mid,
                    rule_type="LOW_BUS_FACTOR",
                    triggering_metric=f"bus_factor={bus_factor}",
                    suggested_action="Identify and train backup maintainers through code pairing and shared reviews.",
                )
            )

        # 2. High Knowledge Concentration (>= 75%)
        if concentration >= 75.0:
            recs.append(
                Recommendation(
                    severity="HIGH" if level in ("HIGH", "CRITICAL") else "MODERATE",
                    title=f"High Knowledge Concentration on {name} ({concentration:.1f}%)",
                    description=(
                        f"Knowledge on '{name}' is concentrated at {concentration:.1f}% HHI. "
                        f"Triggering metric: Concentration exceeds 75% threshold. "
                        f"Suggested action: Conduct structured knowledge-transfer sessions and distribute PR reviews."
                    ),
                    module_id=mid,
                    rule_type="HIGH_KNOWLEDGE_CONCENTRATION",
                    triggering_metric=f"concentration_pct={concentration:.1f}%",
                    suggested_action="Schedule knowledge transfer walkthroughs and rotate PR ownership.",
                )
            )

        # 3. Insufficient Documentation (< 40%)
        if doc_score < 0.4 and level in ("MODERATE", "HIGH", "CRITICAL"):
            recs.append(
                Recommendation(
                    severity="HIGH" if level in ("HIGH", "CRITICAL") else "MODERATE",
                    title=f"Insufficient Documentation on {name} ({round(doc_score * 100)}%)",
                    description=(
                        f"Documentation coverage on '{name}' is only {round(doc_score * 100)}%. "
                        f"Triggering metric: Doc coverage is below 40% threshold for an active module. "
                        f"Suggested action: Document module architecture, public interfaces, and operational runbooks."
                    ),
                    module_id=mid,
                    rule_type="LOW_DOCUMENTATION",
                    triggering_metric=f"doc_coverage_pct={round(doc_score * 100)}%",
                    suggested_action="Add architectural overview and integration test documentation.",
                )
            )

        # 4. High Cyclomatic Complexity (> 15)
        if complexity > 15.0:
            recs.append(
                Recommendation(
                    severity="HIGH" if level in ("HIGH", "CRITICAL") else "MODERATE",
                    title=f"High Cyclomatic Complexity in {name} (avg {complexity:.1f})",
                    description=(
                        f"Average cyclomatic complexity for files in '{name}' is {complexity:.1f}. "
                        f"Triggering metric: Average complexity exceeds 15.0. "
                        f"Suggested action: Decompose complex branching logic, refactor into smaller methods, and add unit tests."
                    ),
                    module_id=mid,
                    rule_type="HIGH_COMPLEXITY",
                    triggering_metric=f"complexity_avg={complexity:.1f}",
                    suggested_action="Refactor high-complexity methods into composable subroutines.",
                )
            )

        # 5. High Code Churn / Change Frequency (>= 50 commits in 90 days)
        if change_freq >= 50 and level in ("MODERATE", "HIGH", "CRITICAL"):
            recs.append(
                Recommendation(
                    severity="MODERATE",
                    title=f"High Code Churn on {name} ({change_freq} commits / 90d)",
                    description=(
                        f"Module '{name}' has experienced frequent modifications ({change_freq} commits in last 90 days). "
                        f"Triggering metric: 90-day change frequency exceeds 50 commits. "
                        f"Suggested action: Require mandatory multi-peer reviews and increase automated regression tests."
                    ),
                    module_id=mid,
                    rule_type="HIGH_CHURN",
                    triggering_metric=f"change_frequency_90d={change_freq}",
                    suggested_action="Enforce strict code review requirements and comprehensive test suites.",
                )
            )

        # 6. High Architectural Centrality (In+Out degree >= 4)
        if centrality >= 4.0 and level in ("HIGH", "CRITICAL"):
            recs.append(
                Recommendation(
                    severity="HIGH",
                    title=f"High Architectural Centrality for {name} ({int(centrality)} connections)",
                    description=(
                        f"Module '{name}' is a high-centrality hub with {int(centrality)} dependency links. "
                        f"Triggering metric: Architectural centrality >= 4 with elevated risk ({score}/100). "
                        f"Suggested action: Perform an architectural review to decouple downstream dependents and isolate boundaries."
                    ),
                    module_id=mid,
                    rule_type="HIGH_CENTRALITY",
                    triggering_metric=f"dependency_centrality={centrality}",
                    suggested_action="Conduct architectural review and define strict public interface boundaries.",
                )
            )

    # 7. Drift flags (Knowledge concentration increasing)
    for d in drift_flags:
        recs.append(
            Recommendation(
                severity="MODERATE",
                title=f"Knowledge Concentration Increasing on {d.get('name', 'Module')}",
                description=(
                    f"{d.get('message', '')}. "
                    f"Triggering metric: Month-over-month single-author lines trend upwards. "
                    f"Suggested action: Distribute upcoming feature development across multiple engineers."
                ),
                module_id=d.get("module_id"),
                rule_type="DRIFT_INCREASING",
                triggering_metric="increasing_concentration_trend",
                suggested_action="Actively allocate tasks in this module to alternative team members.",
            )
        )

    # 8. Critical Areas
    for c in critical_areas:
        cmid = c.get("module_id")
        cname = c.get("name", "Module")
        if not any(r.module_id == cmid and r.severity == "CRITICAL" for r in recs):
            recs.append(
                Recommendation(
                    severity="CRITICAL",
                    title=f"{cname} is a Critical Knowledge Area",
                    description=(
                        f"'{cname}' combines high structural importance with elevated engineering risk. "
                        f"Triggering metric: Criticality score exceeds project threshold. "
                        f"Suggested action: Prioritize knowledge transfer, documentation, and succession planning immediately."
                    ),
                    module_id=cmid,
                    rule_type="CRITICAL_KNOWLEDGE_AREA",
                    triggering_metric="criticality_threshold_exceeded",
                    suggested_action="Formulate a formal succession plan and require backup maintainer approvals.",
                )
            )

    # Severity ranking: CRITICAL=0, HIGH=1, MODERATE=2, LOW=3
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    recs.sort(key=lambda r: severity_order.get(r.severity, 4))
    return recs


KNOWLEDGE_TRANSFER_TOPIC_TEMPLATES = [
    "{module} architectural design and component boundaries",
    "Core data models, state management, and persistence for {module}",
    "Key operational runbooks and deployment procedures for {module}",
    "Common failure modes, error handling, and recovery steps for {module}",
    "Critical APIs, dependency contracts, and integration points for {module}",
    "Testing strategy, regression suites, and debugging workflows for {module}",
]


def generate_knowledge_transfer_plan(module_name: str, backup_developer_id: str | None, priority: str) -> dict:
    return {
        "module": module_name,
        "topics": [t.format(module=module_name) for t in KNOWLEDGE_TRANSFER_TOPIC_TEMPLATES],
        "recommended_backup_developer_id": backup_developer_id,
        "priority": priority,
        "suggested_format": "Pair programming sessions + architectural documentation review",
    }
