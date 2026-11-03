"""
Import every model module here so `Base.metadata` (used by Alembic
autogenerate and by tests that call `Base.metadata.create_all`) always sees
the full schema regardless of which module happens to be imported first.
"""
from app.models.project import Project, Repository  # noqa: F401
from app.models.developer import Developer, DeveloperAlias  # noqa: F401
from app.models.code import (  # noqa: F401
    Module,
    File,
    ModuleDependency,
    Technology,
    DeveloperTechnology,
)
from app.models.activity import (  # noqa: F401
    Commit,
    PullRequest,
    Review,
    Issue,
    DeveloperFileActivity,
    DeveloperModuleActivity,
)
from app.models.analysis import (  # noqa: F401
    AnalysisRun,
    KnowledgeScore,
    RiskScore,
    ResilienceScore,
)
from app.models.simulation import Simulation, SimulationResult, Recommendation  # noqa: F401
