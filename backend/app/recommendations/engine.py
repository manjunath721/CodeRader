"""
Recommendation engine — rule-based, ranked by severity (master spec §22, §30).
Consumes the outputs of the risk engine / drift detector / hidden-expert
detector that already exist for a completed analysis run, and turns them
into concrete, human-readable action items. No recommendation is generated
from a number this module invents itself — every one cites a real score.
"""
from dataclasses import dataclass


@dataclass
class Recommendation:
    severity: str  # CRITICAL|HIGH|MODERATE
    title: str
    description: str
    module_id: str | None = None
    related_developer_id: str | None = None


def generate_recommendations(
    module_risks: list[dict],  # [{module_id, name, score, level, bus_factor, documentation_score}]
    drift_flags: list[dict],  # [{module_id, name, message}]
    critical_areas: list[dict],  # [{module_id, name}]
) -> list[Recommendation]:
    recs: list[Recommendation] = []

    for m in module_risks:
        if m["bus_factor"] <= 1 and m["level"] in ("HIGH", "CRITICAL"):
            recs.append(
                Recommendation(
                    severity="CRITICAL",
                    title=f"{m['name']} has a bus factor of {m['bus_factor']}.",
                    description=(
                        f"Assign a secondary repository-derived knowledge owner to {m['name']} "
                        f"(risk score {m['score']}/100)."
                    ),
                    module_id=m["module_id"],
                )
            )
        if m["documentation_score"] < 0.4 and m["level"] in ("MODERATE", "HIGH", "CRITICAL"):
            recs.append(
                Recommendation(
                    severity="HIGH" if m["level"] in ("HIGH", "CRITICAL") else "MODERATE",
                    title=f"{m['name']} documentation is insufficient.",
                    description=(
                        f"Documentation coverage is {round(m['documentation_score'] * 100)}%. "
                        f"Document {m['name']}'s architecture and key operational procedures."
                    ),
                    module_id=m["module_id"],
                )
            )

    for d in drift_flags:
        recs.append(
            Recommendation(
                severity="MODERATE",
                title=f"Knowledge concentration on {d['name']} is increasing.",
                description=d["message"] + " Distribute upcoming work across additional contributors.",
                module_id=d["module_id"],
            )
        )

    for c in critical_areas:
        if not any(r.module_id == c["module_id"] and r.severity == "CRITICAL" for r in recs):
            recs.append(
                Recommendation(
                    severity="CRITICAL",
                    title=f"{c['name']} is a critical knowledge area.",
                    description=(
                        f"{c['name']} combines high structural importance with high risk. "
                        "Prioritize knowledge-transfer and backup-owner assignment here first."
                    ),
                    module_id=c["module_id"],
                )
            )

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2}
    recs.sort(key=lambda r: severity_order.get(r.severity, 3))
    return recs


KNOWLEDGE_TRANSFER_TOPIC_TEMPLATES = [
    "{module} architecture overview",
    "Core integration points for {module}",
    "Key operational/runbook knowledge for {module}",
    "Common failure modes and recovery steps for {module}",
    "{module} data model and storage structure",
]


def generate_knowledge_transfer_plan(module_name: str, backup_developer_id: str | None, priority: str) -> dict:
    """master spec §22."""
    return {
        "module": module_name,
        "topics": [t.format(module=module_name) for t in KNOWLEDGE_TRANSFER_TOPIC_TEMPLATES],
        "recommended_backup_developer_id": backup_developer_id,
        "priority": priority,
    }
