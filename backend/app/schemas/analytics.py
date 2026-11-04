import uuid

from pydantic import BaseModel


class ModuleSummary(BaseModel):
    id: uuid.UUID
    name: str
    risk_score: float | None
    risk_level: str | None
    bus_factor: int | None
    concentration_pct: float | None
    is_critical_knowledge_area: bool = False


class DeveloperSummary(BaseModel):
    id: uuid.UUID
    display_name: str
    modules_count: int
    critical_ownership_count: int
    single_owner_modules_count: int


class RiskDistribution(BaseModel):
    LOW: int = 0
    MODERATE: int = 0
    HIGH: int = 0
    CRITICAL: int = 0


class DashboardOut(BaseModel):
    project_id: uuid.UUID
    project_name: str
    is_demo: bool
    resilience_score: float | None
    resilience_label: str | None
    risk_distribution: RiskDistribution
    top_risk_modules: list[ModuleSummary]
    critical_knowledge_areas: list[ModuleSummary]
    developer_count: int
    module_count: int
    last_analysis_run_id: uuid.UUID | None
    last_analyzed_at: str | None


class ModuleDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    path_prefix: str
    risk_score: float | None
    risk_level: str | None
    risk_factors: dict | None
    bus_factor: int | None
    concentration_pct: float | None
    documentation_score: float
    complexity_avg: float
    change_frequency_90d: int
    is_critical_knowledge_area: bool = False
    knowledge_distribution: list[dict]  # [{developer_id, developer_name, score}]
    backup_candidates: list[dict]
    dependencies: list[str]
    dependents: list[str]


class DeveloperDetailOut(BaseModel):
    id: uuid.UUID
    display_name: str
    primary_email: str | None
    modules: list[dict]  # [{module_id, module_name, score}]
    critical_ownership_count: int
    single_owner_modules_count: int
    dependency_risk: str  # LOW|MODERATE|HIGH


class RecommendationOut(BaseModel):
    id: uuid.UUID
    severity: str
    title: str
    description: str
    module_id: uuid.UUID | None = None
    related_developer_id: uuid.UUID | None = None


class KnowledgeTransferRequest(BaseModel):
    module_name: str
    backup_developer_id: str | None = None
    priority: str = "HIGH"


class KnowledgeTransferPlanOut(BaseModel):
    module: str
    topics: list[str]
    recommended_backup_developer_id: str | None = None
    priority: str
    suggested_format: str


class SimulationRequest(BaseModel):
    project_id: uuid.UUID
    developer_id: uuid.UUID | None = None
    developer_ids: list[uuid.UUID] | None = None


class SimulationOut(BaseModel):
    simulation_id: uuid.UUID
    resilience_before: float
    resilience_after: float
    resilience_label_before: str
    resilience_label_after: str
    knowledge_impact_pct: float
    affected_modules: list[dict]  # [{id, name}]
    backup_candidates: dict
    risk_propagation: dict
