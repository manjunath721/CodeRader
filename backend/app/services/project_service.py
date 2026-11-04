"""
Project deletion with FK-safe ordered cleanup.

ORM cascades only cover Project -> repositories/developers/analysis_runs,
so a naive `db.delete(project)` would violate foreign keys from
modules/files/scores/simulations (Postgres) or leave orphan rows (SQLite).
Deletion therefore removes children before parents, in dependency order —
children that reference the project's repos, modules, developers, and runs.
"""
from sqlalchemy.orm import Session

from app.models.activity import (
    Commit,
    DeveloperFileActivity,
    DeveloperModuleActivity,
    Issue,
    PullRequest,
    Review,
)
from app.models.analysis import AnalysisRun, KnowledgeScore, ResilienceScore, RiskScore
from app.models.code import DeveloperTechnology, File, Module, ModuleDependency
from app.models.developer import Developer, DeveloperAlias
from app.models.project import Project, Repository
from app.models.simulation import Recommendation, Simulation, SimulationResult


def delete_project(db: Session, project: Project) -> None:
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    dev_ids = [d.id for d in db.query(Developer).filter(Developer.project_id == project.id)]
    run_ids = [r.id for r in db.query(AnalysisRun).filter(AnalysisRun.project_id == project.id)]
    module_ids = (
        [m.id for m in db.query(Module).filter(Module.repository_id.in_(repo_ids))] if repo_ids else []
    )
    file_ids = (
        [f.id for f in db.query(File).filter(File.repository_id.in_(repo_ids))] if repo_ids else []
    )
    pr_ids = (
        [p.id for p in db.query(PullRequest).filter(PullRequest.repository_id.in_(repo_ids))]
        if repo_ids
        else []
    )

    if run_ids:
        sim_ids = [s.id for s in db.query(Simulation).filter(Simulation.project_id == project.id)]
        if sim_ids:
            db.query(SimulationResult).filter(SimulationResult.simulation_id.in_(sim_ids)).delete(
                synchronize_session=False
            )
        db.query(Simulation).filter(Simulation.project_id == project.id).delete(
            synchronize_session=False
        )
        db.query(KnowledgeScore).filter(KnowledgeScore.analysis_run_id.in_(run_ids)).delete(
            synchronize_session=False
        )
        db.query(RiskScore).filter(RiskScore.analysis_run_id.in_(run_ids)).delete(
            synchronize_session=False
        )
    db.query(ResilienceScore).filter(ResilienceScore.project_id == project.id).delete(
        synchronize_session=False
    )
    db.query(Recommendation).filter(Recommendation.project_id == project.id).delete(
        synchronize_session=False
    )

    if dev_ids:
        db.query(DeveloperFileActivity).filter(DeveloperFileActivity.developer_id.in_(dev_ids)).delete(
            synchronize_session=False
        )
        db.query(DeveloperTechnology).filter(DeveloperTechnology.developer_id.in_(dev_ids)).delete(
            synchronize_session=False
        )
        db.query(DeveloperAlias).filter(DeveloperAlias.developer_id.in_(dev_ids)).delete(
            synchronize_session=False
        )
    if module_ids:
        db.query(DeveloperModuleActivity).filter(
            DeveloperModuleActivity.module_id.in_(module_ids)
        ).delete(synchronize_session=False)
        db.query(ModuleDependency).filter(ModuleDependency.module_id.in_(module_ids)).delete(
            synchronize_session=False
        )
        db.query(ModuleDependency).filter(ModuleDependency.depends_on_module_id.in_(module_ids)).delete(
            synchronize_session=False
        )
    if file_ids:
        db.query(DeveloperFileActivity).filter(DeveloperFileActivity.file_id.in_(file_ids)).delete(
            synchronize_session=False
        )
    if pr_ids:
        db.query(Review).filter(Review.pull_request_id.in_(pr_ids)).delete(synchronize_session=False)
    if repo_ids:
        db.query(PullRequest).filter(PullRequest.repository_id.in_(repo_ids)).delete(
            synchronize_session=False
        )
        db.query(Issue).filter(Issue.repository_id.in_(repo_ids)).delete(synchronize_session=False)
        db.query(Commit).filter(Commit.repository_id.in_(repo_ids)).delete(synchronize_session=False)
        db.query(File).filter(File.repository_id.in_(repo_ids)).delete(synchronize_session=False)
        db.query(Module).filter(Module.repository_id.in_(repo_ids)).delete(synchronize_session=False)
        db.query(Repository).filter(Repository.project_id == project.id).delete(
            synchronize_session=False
        )
    if dev_ids:
        db.query(Developer).filter(Developer.project_id == project.id).delete(
            synchronize_session=False
        )
    if run_ids:
        db.query(AnalysisRun).filter(AnalysisRun.project_id == project.id).delete(
            synchronize_session=False
        )
    from app.models.auth import ProjectMember
    db.query(ProjectMember).filter(ProjectMember.project_id == project.id).delete(synchronize_session=False)
    db.query(Project).filter(Project.id == project.id).delete(synchronize_session=False)
    db.commit()
