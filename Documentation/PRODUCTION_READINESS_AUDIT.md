# CodeRadar Production Readiness Audit (Initial)

**Audit basis:** repository source, Alembic migrations, tests, dependency/configuration files, README and existing `project_documentation/` reference materials. Initial review; implementation and runtime verification remain in progress. `.env` was intentionally not read. Existing untracked `project_documentation/` is preserved.

## Current architecture

CodeRadar is a React 18/TypeScript/Vite SPA calling a FastAPI REST API under `/api`. SQLAlchemy 2 and Alembic persist data in PostgreSQL; tests are designed to use SQLite. Repository ingestion invokes Git CLI/GitPython, source parsers, NetworkX graphs and deterministic scoring/simulation engines. Analysis runs as FastAPI in-process `BackgroundTasks`; optional Anthropic answering is configured separately. Docker Compose declares PostgreSQL, backend, and frontend services.

## Existing functionality (source-level; runtime status varies)

- Project and repository records, repository cloning/local ingestion, Git history extraction and identity normalization.
- Source-file/module detection, import-derived dependency edges, Git activity aggregates and incremental content-hash/checkpoint logic.
- Run-scoped knowledge/risk/resilience/recommendation results, dashboard and detail APIs, graph data, simulations, and a React UI including Knowledge Cosmos and AI Analyst.
- Three Alembic revisions, Docker/Compose files, and backend/frontend test definitions.
- No implemented authentication/authorization, durable job queue, GitHub review/issue ingestion, or trained ML model. Metrics are repository-derived estimates, not measures of human performance.

## Critical issues and important technical debt

### Critical before any multi-user/non-local deployment

1. **No authentication or authorization:** project and simulation endpoints are accessible to any caller who can reach the API; there is no tenant/owner boundary.
2. **Untrusted repository work is exposed through the API process:** URL screening and clone limits exist, but DNS rebinding/network egress, per-user quotas, worker isolation and durable retries are not solved. In-process jobs can be lost on restart and compete with API resources.
3. **RESOLVED in this checkpoint — sensitive failure detail disclosure:** `run_analysis` previously stored `str(exc)` in `AnalysisRun.error_message`; it now persists a generic message while keeping diagnostics in server-side logs. Other exception surfaces still need testing.

### High-priority correctness/reliability issues

4. **Repository reconciliation is incomplete:** rewritten Git history can leave unreachable commit/activity aggregates; removed modules and stale dependency edges can contaminate new analysis. File deletion is handled more completely than module/edge deletion. Incremental-vs-full equivalence is not established by regression tests.
5. **Project risk settings are stored but not applied:** the analysis pipeline calls risk engines without project configuration.
6. **Metric gaps:** module LOC/criticality proxy is not populated, review/issue/technology signals are unavailable and must not be presented as measured data; configured commit ceiling appears unused.
7. **Partial persistence:** pipeline commits multiple times. Failed/cancelled runs are hidden from completed-run reads but intermediate mutable ingestion facts remain.
8. **Input/operational controls:** no rate limiting, auth failure/audit events, request-size policy, request correlation, or database readiness probe. Simulation developer IDs are not verified against the requested project.

### Important product/tooling/documentation debt

9. Frontend uses hand-managed fetch state despite a mounted TanStack Query provider. Frontend tests/build now run; lint remains blocked by missing ESLint flat configuration. Docker/Compose cannot start without the Docker daemon in this environment.
10. The original README claimed GitHub API/review ingestion and extensive completed phases/tests that did not match the implementation. The root README has been corrected here; older `docs/` and pre-existing `project_documentation/` materials still require a full cross-document reconciliation.
11. No CI workflow, structured application logging/metrics/tracing, restore-tested backup policy, durable worker, or production Docker profile is present.
12. SSRF validation previously accepted mixed public/private DNS answers and hosts with no DNS records; this was tightened to fail closed for both cases. **DNS rebinding remains possible** because Git resolves the hostname again at clone time. Clone size/file-count budgets are enforced after cloning, so they do not cap clone-time disk use.
13. Additional ingestion defects were confirmed and fixed: a Full Scan after a Quick Scan now backfills omitted commit history; repository commit counts no longer double-count inserted rows; obsolete auto-generated import edges are removed while manual edges are retained.
14. Identity reconciliation now keeps a no-email author separate from an email-backed author with the same normalized name instead of silently merging solely by name.
15. Remaining ingestion limitations include stale modules after deleted directories/renames, force-push history aggregates, and the configured `MAX_COMMITS_PER_RUN` ceiling not being applied to Full Scan.
16. Deployment/tooling evidence: fresh Compose relies on an externally named pre-existing Postgres volume; Compose uses dev servers/reload and publishes services, no CI workflow was found; `DEBUG` defaults to true. Frontend `npm run lint` fails because ESLint 9 flat config is missing. `npm ci` reported 15 audit findings (10 moderate, 3 high, 2 critical); production-dependency-only audit reported two moderate React Router advisories. Do not run `npm audit fix --force` without reviewing the major-version upgrade.

## Baseline verification (this session)

- Git history: one visible commit, `a9fef20 Initial project import`; `main` matches `origin/main` at start.
- Pre-existing working tree: untracked `project_documentation/`; left untouched.
- Backend test command `python -m pytest backend/tests -q` could not start because the ambient Python lacks `pytest`. Re-running in an isolated `uv run --with-requirements` environment produced **48 passed, 1 third-party deprecation warning** after the Phase 1 fixes below. No backend tests failed in the passing run.
- Frontend: `npm ci` completed (with engine/deprecation/audit warnings); `npm test`: **11 passed**; `npm run build`: **succeeded**; `npm run lint`: **BLOCKED** because no ESLint 9 flat config exists.
- npm audit: install reported 15 findings (10 moderate, 3 high, 2 critical); `npm audit --omit=dev` reports 2 moderate React Router findings. No forced dependency upgrades were applied.
- Docker Compose CLI is installed, but engine query failed because the Docker Desktop Linux engine named pipe is unavailable; no Compose build/start was performed.

## Changes implemented during this checkpoint

- **COMPLETE (error disclosure):** analysis failures persist a generic user-facing message instead of `str(exception)`. Detailed traceback remains in server-side exception logging with analysis/project correlation IDs.
- **COMPLETE (incremental scan correctness):** a Full Scan after a prior Quick Scan no longer resumes from the Quick Scan checkpoint; it backfills omitted reachable history.
- **COMPLETE (data correctness):** repository commit counts now reflect persisted commit rows exactly; incremental import-edge reconciliation removes stale auto-generated edges while preserving manual edges.
- **COMPLETE (identity correctness for new grouping):** no-email authors are no longer silently merged into an email-backed identity solely because normalized names match. Existing database rows that were previously merged are not automatically split.
- **COMPLETE (SSRF validation hardening):** reject DNS answers if none are returned or if any returned address is private/local/reserved. This does not prevent DNS rebinding between validation and Git's later resolution.
- Added regressions first and confirmed RED for error disclosure, Quick-to-Full backfill, dependency-edge cleanup, identity merging, and repository counts; focused tests then passed.
- Backend suite: **48 passed, 1 warning**. Frontend suite: **11 passed**; production TypeScript/Vite build succeeded.

## Implementation sequence and dependencies

1. **Stabilize/validate baseline:** provision an isolated test environment; collect backend/frontend test/build results; correct actual runtime blockers before relying on prior assessment claims.
2. **Phase 1 correctness:** continue regression coverage and snapshot reconciliation. Precisely define reachable commits/current files/modules/edges, transaction boundaries, and safe migration needs. Do not make destructive schema changes without a reversible migration.
3. **Phase 2 security:** design identity/tenant ownership before endpoint authorization; validate project access on every route, then add URL/SSRF/resource and API controls with negative tests. Authentication must precede multi-user deployment.
4. **Phase 3 reliability:** durable queue/workers require idempotent analysis state transitions and reconciliation semantics; retain progress/cancellation contracts while isolating Git work.
5. **Phases 4–6 analytical/data/API quality:** apply validated/versioned risk config and clarify evidence availability before score changes; version scoring and add migration tests before changing persisted contracts.
6. **Phases 7–9 product/AI:** improve UI/testing and constrain AI to authorized, provenance-backed data after security/data contracts exist.
7. **Phases 10–15:** no ML until labeled data; add CI, container/runtime checks and observability; update docs from implemented facts; final audit only after tests/builds/deployment checks actually run.

## Dependencies and risks of modification

- Ingestion, `developer_module_activity`, commit `module_changes`, module paths, and dependency edges jointly feed risk and drift. Reconciliation changes can invalidate historical aggregates and risk scores; write regression tests and preserve existing snapshots before modifying these flows.
- Risk formulas affect dashboard, recommendations, simulations and AI context. Do not alter weights without reproducibility tests and explicit versioning.
- API response models feed a manually typed frontend client. Contract edits must be tested on both sides.
- Existing docs under `project_documentation/` were untracked at start; do not overwrite them without reviewing the resulting diff. Avoid database resets or destructive migrations.

## Readiness assessment

**NOT PRODUCTION READY.** Authentication/authorization, safe isolated analysis execution, full snapshot reconciliation, DNS rebinding controls, frontend lint/dependency review, and executed Docker/production deployment validation remain outstanding. Error redaction and several Phase 1 correctness regressions were fixed and tested in this checkpoint; this is not a final readiness report.
