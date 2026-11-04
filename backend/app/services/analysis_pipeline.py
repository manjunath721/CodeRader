"""
Full analysis pipeline orchestration (architecture.md §3, stages 1-17) —
perf-hardened version.

Changed from the original design (see Documentation/PERFORMANCE_BENCHMARKS.md for the
measurements behind these decisions):

- No longer wipes and fully re-ingests a repository on every run
  (`_reset_repository_data` is gone). `ingest_repository` now does
  incremental, idempotent-retry-safe ingestion itself — see
  app/services/ingestion_service.py.
- Knowledge-score input (per developer x module commit/line activity) is
  read directly from the `developer_module_activity` table, which ingestion
  now maintains as a running cumulative aggregate, instead of being rebuilt
  from scratch by scanning every historical Commit row on every single
  analysis run. This was the dominant *analysis-side* cost for a
  long-lived, frequently-re-analyzed repository: O(all-time commits) Python
  work on every run regardless of how many commits were actually new.
- Knowledge drift still reads the full Commit history, because detecting a
  multi-month trend genuinely requires the full time series — but that's
  now just a single indexed SELECT (no git operations, no per-row writes),
  nowhere near the cost profile of what was removed above.
- Cooperative cancellation: the run's `cancel_requested` flag (set via
  POST .../analysis-runs/{id}/cancel) is checked between stages. A
  cancelled run is marked "cancelled", not "complete" or "failed", and
  nothing it wrote is ever surfaced by the read APIs — every dashboard/
  risk/resilience query filters to the latest run with status == "complete"
  (see query_service.get_latest_complete_run), so a cancelled or failed
  run's partial writes are simply never published, by construction.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.graph.dependency_graph import build_dependency_graph, dependency_concentration_hhi
from app.models.activity import Commit, DeveloperModuleActivity
from app.models.analysis import AnalysisRun, KnowledgeScore, ResilienceScore, RiskScore
from app.models.code import File as FileModel
from app.models.code import Module, ModuleDependency
from app.models.developer import Developer
from app.models.project import Project, Repository
from app.models.simulation import Recommendation
from app.recommendations.engine import generate_recommendations
from app.risk.drift import DriftPoint, detect_drift
from app.risk.hidden_experts import ExpertSignal, detect_hidden_experts
from app.risk.knowledge import ModuleActivity, bus_factor, compute_module_knowledge_scores, knowledge_concentration_hhi
from app.risk.risk_engine import ModuleRiskInput, ResilienceInput, compute_criticality, compute_module_risks, compute_resilience_score
from app.services.ingestion_service import ingest_repository


class AnalysisCancelledError(Exception):
    """Raised internally to unwind run_analysis cleanly on cancellation —
    deliberately NOT a subclass of the generic failure path, so a cancelled
    run is recorded as status='cancelled', not 'failed'."""


def run_analysis(db: Session, project: Project, run: AnalysisRun | None = None) -> AnalysisRun:
    if run is None:
        run = AnalysisRun(project_id=project.id, status="running", stage_status={}, started_at=datetime.now(timezone.utc))
        db.add(run)
        db.commit()
        db.refresh(run)
    else:
        run.status = "running"
        run.started_at = run.started_at or datetime.now(timezone.utc)
        db.add(run)
        db.commit()

    stages: dict[str, str] = {}
    progress: dict = {}

    def mark(stage: str, status: str = "complete", **progress_update) -> None:
        stages[stage] = status
        progress.update(progress_update)
        db.refresh(run)
        if run.cancel_requested:
            raise AnalysisCancelledError()
        run.stage_status = dict(stages)
        run.progress = dict(progress)
        db.add(run)
        db.commit()

    risk_cfg = project.risk_config or {}
    previous_checkpoints = {
        r.id: (r.last_indexed_commit_sha, r.last_indexed_branch, r.last_analyzed_at, r.scan_mode)
        for r in db.query(Repository).filter(Repository.project_id == project.id).all()
    }

    try:
        # --- Stages 1-9: incremental ingestion (per repository) ---
        ingestion_summary: dict[str, dict] = {}
        for repo in db.query(Repository).filter(Repository.project_id == project.id):
            summary = ingest_repository(
                db, repo, repo.url, is_local=(repo.provider == "local"), scan_mode=run.scan_mode,
            )
            ingestion_summary[str(repo.id)] = summary
        mark("repository_ingestion", ingestion=ingestion_summary)

        repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
        modules = db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()
        mark("commit_analysis")

        # --- Stage: knowledge-scoring input, read directly from the
        #     cumulative DeveloperModuleActivity aggregate (perf: see
        #     module docstring — this used to rescan every historical
        #     commit on every run) ---
        now = datetime.now(timezone.utc)
        module_ids = [m.id for m in modules]
        activity_rows = (
            db.query(DeveloperModuleActivity).filter(DeveloperModuleActivity.module_id.in_(module_ids)).all()
            if module_ids else []
        )
        activity: dict[str, dict[str, ModuleActivity]] = defaultdict(dict)
        for row in activity_rows:
            last_at = row.last_activity_at
            if last_at and last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            activity[str(row.module_id)][str(row.developer_id)] = ModuleActivity(
                commits_count=row.commits_count, lines_changed=row.lines_changed, last_commit_at=last_at,
            )
        mark("knowledge_scoring")

        # --- Stage: knowledge scores per module ---
        knowledge_weights = risk_cfg.get("knowledge_weights")
        half_life_days = risk_cfg.get("recency_half_life_days")
        knowledge_by_module: dict[str, dict[str, float]] = {}
        for mod_id, dev_activities in activity.items():
            results = compute_module_knowledge_scores(
                mod_id, dev_activities, now=now, weights=knowledge_weights, half_life_days=half_life_days,
            )
            knowledge_by_module[mod_id] = {r.developer_id: r.score for r in results}
            for r in results:
                db.add(
                    KnowledgeScore(
                        analysis_run_id=run.id, developer_id=r.developer_id, module_id=r.module_id,
                        score=r.score, component_breakdown=r.components, computed_at=now,
                    )
                )
        db.commit()

        # --- Stage: 90-day change frequency + monthly drift series. Needs a
        #     full-history read by nature (a multi-month trend can't be
        #     derived from only the newest commits) — but it's now just one
        #     indexed SELECT, not a git/diff/per-row-write operation. ---
        ninety_days_ago = now - timedelta(days=90)
        change_freq_90d: dict[str, int] = defaultdict(int)
        monthly_module_dev_lines: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
        module_by_prefix = {m.path_prefix: m for m in modules}

        commits = db.query(Commit).filter(Commit.repository_id.in_(repo_ids)).all()
        for c in commits:
            if not c.developer_id:
                continue
            dev_id = str(c.developer_id)
            authored_at = c.authored_at if c.authored_at.tzinfo else c.authored_at.replace(tzinfo=timezone.utc)
            month_key = authored_at.strftime("%Y-%m")
            for module_prefix, lines in (c.module_changes or {}).items():
                module = module_by_prefix.get(module_prefix)
                if not module:
                    continue
                mod_id = str(module.id)
                monthly_module_dev_lines[mod_id][month_key][dev_id] = (
                    monthly_module_dev_lines[mod_id][month_key].get(dev_id, 0) + lines
                )
                if authored_at >= ninety_days_ago:
                    change_freq_90d[mod_id] += 1

        # --- Stage: module facts (docs, complexity, LOC) from Files ---
        module_doc_score: dict[str, float] = {}
        module_complexity: dict[str, float] = {}
        module_loc: dict[str, int] = {}
        for m in modules:
            files = db.query(FileModel).filter(FileModel.module_id == m.id).all()
            if files:
                module_doc_score[str(m.id)] = sum(f.doc_coverage_pct for f in files) / len(files) / 100
                module_complexity[str(m.id)] = sum(f.complexity for f in files) / len(files)
                m.loc = sum(
                    f.lines_of_code if getattr(f, "lines_of_code", 0) > 0 else max(f.size_bytes // 35, 1)
                    for f in files
                )
            else:
                module_doc_score[str(m.id)] = 0.0
                module_complexity[str(m.id)] = 0.0
                m.loc = 0
            module_loc[str(m.id)] = m.loc
            m.documentation_score = module_doc_score[str(m.id)]
            m.complexity_avg = module_complexity[str(m.id)]
            m.change_frequency_90d = change_freq_90d.get(str(m.id), 0)
            db.add(m)
        db.commit()
        mark("graph_construction")

        # --- Stage: dependency graph + centrality (now populated by
        #     automatic import-based extraction in ingestion, in addition to
        #     any manually/demo-seeded edges) ---
        dep_rows = db.query(ModuleDependency).filter(ModuleDependency.module_id.in_([m.id for m in modules])).all()
        dep_edges = [(str(d.module_id), str(d.depends_on_module_id)) for d in dep_rows]
        dep_graph = build_dependency_graph(dep_edges)
        centrality = {n: dep_graph.in_degree(n) + dep_graph.out_degree(n) for n in dep_graph.nodes}
        dep_concentration = dependency_concentration_hhi(dep_graph)
        mark("risk_calculation")

        # --- Stage: module risk + criticality + bus factor ---
        risk_inputs = []
        module_meta = {}
        for m in modules:
            mid = str(m.id)
            scores = knowledge_by_module.get(mid, {})
            concentration = knowledge_concentration_hhi(list(scores.values())) if scores else 0.0
            bf = bus_factor(scores) if scores else 0
            module_meta[mid] = {"concentration": concentration, "bus_factor": bf, "name": m.name}
            risk_inputs.append(
                ModuleRiskInput(
                    module_id=mid, concentration_pct=concentration, bus_factor=bf,
                    documentation_score=module_doc_score.get(mid, 0.0),
                    complexity_avg=module_complexity.get(mid, 0.0),
                    change_frequency_90d=change_freq_90d.get(mid, 0),
                    dependency_centrality=float(centrality.get(mid, 0)),
                )
            )
        risk_weights = risk_cfg.get("risk_weights")
        risk_results = compute_module_risks(risk_inputs, weights=risk_weights)
        centrality_norm = {}
        if centrality:
            max_c = max(centrality.values()) or 1
            centrality_norm = {k: v / max_c for k, v in centrality.items()}
        max_change = max(change_freq_90d.values(), default=0) or 1

        total_loc = sum(module_loc.values()) or 1
        criticality_threshold = risk_cfg.get("criticality_threshold")
        risk_rows_by_module = {}
        for rr in risk_results:
            centrality_n = centrality_norm.get(rr.module_id, 0.0)
            change_n = change_freq_90d.get(rr.module_id, 0) / max_change
            loc_share = module_loc.get(rr.module_id, 0) / total_loc
            criticality, is_critical = compute_criticality(
                rr.score, centrality_n, change_n, loc_share, threshold=criticality_threshold
            )
            row = RiskScore(
                analysis_run_id=run.id, module_id=rr.module_id, score=rr.score, level=rr.level,
                factors=rr.factors, criticality_score=criticality, is_critical_knowledge_area=is_critical,
                bus_factor=module_meta[rr.module_id]["bus_factor"],
                concentration_pct=module_meta[rr.module_id]["concentration"], computed_at=now,
            )
            db.add(row)
            risk_rows_by_module[rr.module_id] = row
        db.commit()

        # --- Stage: project resilience ---
        bus_factors = [module_meta[mid]["bus_factor"] for mid in module_meta]
        avg_bf = sum(bus_factors) / len(bus_factors) if bus_factors else 0
        max_bf = max(bus_factors, default=1) or 1
        concentrations = [module_meta[mid]["concentration"] for mid in module_meta]
        avg_conc = sum(concentrations) / len(concentrations) if concentrations else 0
        avg_doc = sum(module_doc_score.values()) / len(module_doc_score) if module_doc_score else 0
        critical_scores = [r.score for r in risk_results if r.level in ("HIGH", "CRITICAL")]
        avg_critical = sum(critical_scores) / len(critical_scores) if critical_scores else 0.0

        resilience_score, label, breakdown = compute_resilience_score(
            ResilienceInput(
                avg_bus_factor_norm=avg_bf / max_bf if max_bf else 0.0,
                avg_knowledge_distribution=1 - (avg_conc / 100),
                avg_documentation_coverage=avg_doc,
                avg_critical_module_risk=avg_critical,
                dependency_concentration=dep_concentration,
            )
        )
        db.add(
            ResilienceScore(
                analysis_run_id=run.id, project_id=project.id, score=resilience_score, label=label,
                component_breakdown=breakdown, computed_at=now,
            )
        )
        db.commit()

        # --- Stage: knowledge drift (monthly replay per module's top developer) ---
        drift_flags = []
        for mod_id, monthly in monthly_module_dev_lines.items():
            months_sorted = sorted(monthly.keys())
            if len(months_sorted) < 3:
                continue
            cumulative: dict[str, int] = defaultdict(int)
            series_by_dev: dict[str, list[DriftPoint]] = defaultdict(list)
            for month in months_sorted:
                for dev_id, lines in monthly[month].items():
                    cumulative[dev_id] += lines
                total = sum(cumulative.values()) or 1
                for dev_id, total_lines in cumulative.items():
                    series_by_dev[dev_id].append(DriftPoint(month, round(100 * total_lines / total, 2)))
            top_dev = max(cumulative, key=cumulative.get) if cumulative else None
            if top_dev:
                result = detect_drift(mod_id, top_dev, series_by_dev[top_dev])
                if result.increasing:
                    drift_flags.append(
                        {"module_id": mod_id, "name": module_meta[mod_id]["name"], "message": result.message}
                    )
        mark("recommendations")

        # --- Stage: hidden experts (per module) ---
        for mod_id, dev_activities in activity.items():
            scores = knowledge_by_module.get(mod_id, {})
            if not scores:
                continue
            primary = max(scores, key=scores.get)
            signals = [
                ExpertSignal(developer_id=dev_id, reviews_count=0, issues_count=0)
                for dev_id in dev_activities
            ]
            detect_hidden_experts(signals, primary)  # computed for API exposure via risk breakdown; not persisted separately in MVP

        # --- Stage: recommendations ---
        module_risk_dicts = [
            {
                "module_id": rr.module_id, "name": module_meta[rr.module_id]["name"], "score": rr.score,
                "level": rr.level, "bus_factor": module_meta[rr.module_id]["bus_factor"],
                "documentation_score": module_doc_score.get(rr.module_id, 0.0),
                "concentration_pct": module_meta[rr.module_id]["concentration"],
                "complexity_avg": module_complexity.get(rr.module_id, 0.0),
                "change_frequency_90d": change_freq_90d.get(rr.module_id, 0),
                "dependency_centrality": float(centrality.get(rr.module_id, 0)),
            }
            for rr in risk_results
        ]
        critical_areas = [
            {"module_id": mid, "name": module_meta[mid]["name"]}
            for mid, row in risk_rows_by_module.items()
            if row.is_critical_knowledge_area
        ]
        recs = generate_recommendations(module_risk_dicts, drift_flags, critical_areas)
        for r in recs:
            db.add(
                Recommendation(
                    project_id=project.id, module_id=r.module_id, analysis_run_id=run.id,
                    severity=r.severity, title=r.title, description=r.description,
                    related_developer_id=r.related_developer_id,
                )
            )
        db.commit()

        for repo in db.query(Repository).filter(Repository.project_id == project.id):
            if repo.last_indexed_commit_sha and not run.commit_sha:
                run.commit_sha = repo.last_indexed_commit_sha

        run.status = "complete"
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    except AnalysisCancelledError:
        # Restore repository checkpoints so a cancelled run doesn't advance checkpoint
        for repo_id, (prev_sha, prev_br, prev_at, prev_mode) in previous_checkpoints.items():
            repo = db.get(Repository, repo_id)
            if repo:
                repo.last_indexed_commit_sha = prev_sha
                repo.last_indexed_branch = prev_br
                repo.last_analyzed_at = prev_at
                repo.scan_mode = prev_mode
                db.add(repo)
        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    except Exception:  # noqa: BLE001 - record safe public failure and preserve diagnostics in server logs
        logging.getLogger(__name__).exception(
            "Analysis run failed", extra={"analysis_run_id": str(run.id), "project_id": str(project.id)}
        )
        # Restore repository checkpoints so a failed run never advances the checkpoint
        for repo_id, (prev_sha, prev_br, prev_at, prev_mode) in previous_checkpoints.items():
            repo = db.get(Repository, repo_id)
            if repo:
                repo.last_indexed_commit_sha = prev_sha
                repo.last_indexed_branch = prev_br
                repo.last_analyzed_at = prev_at
                repo.scan_mode = prev_mode
                db.add(repo)
        run.status = "failed"
        run.error_message = "Analysis failed. Please retry or contact support."
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        raise
