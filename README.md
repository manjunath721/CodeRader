# CodeRadar

**AI-Powered Software Team Knowledge & Risk Analyzer** — a capstone project
that analyzes Git/GitHub repository activity to answer: *is critical
technical knowledge dangerously concentrated among too few developers, and
what should the team do about it?*

CodeRadar is **not** a developer productivity tracker. Every metric it
produces is explicitly labeled as a repository-derived estimate and is
traceable back to the commits, reviews, and files that produced it.

## Project status

Phases 1–13 are implemented and tested end-to-end (backend + frontend + full
API integration). Phase 14 (Docker) is configured but unverified in this
environment (no Docker daemon available at build time — see Limitations).
Phase 15 (final documentation polish) is this README pass. See
[Roadmap](#roadmap) for the phase-by-phase breakdown.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system architecture, module responsibilities, pipeline stages
- [`docs/database-schema.md`](docs/database-schema.md) — ER design
- [`docs/api.md`](docs/api.md) — REST API specification
- [`docs/analysis-methodology.md`](docs/analysis-methodology.md) — knowledge scoring, concentration, bus factor, drift, hidden experts — with formulas
- [`docs/risk-model.md`](docs/risk-model.md) — risk score, criticality, resilience score, propagation, simulation, ML layer — with formulas
- [`docs/demo.md`](docs/demo.md) — synthetic demo dataset and the acceptance-criteria demo script
- [`docs/perf-benchmarks.md`](docs/perf-benchmarks.md) — measured before/after performance results for the incremental-indexing pass (git extraction, DB writes, cold vs. incremental re-analysis)

## Tech stack

Frontend: React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Recharts, React Flow, Lucide.
Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
Database: PostgreSQL.
Analysis: GitPython, GitHub REST API, pandas, NumPy, NetworkX, scikit-learn.
DevOps: Docker, Docker Compose, pytest, ESLint, Prettier.

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (or use the provided Docker Compose service)
- Docker & Docker Compose (recommended for local setup)

## Running locally (Docker Compose — recommended)

```bash
cp .env.example .env
docker compose up --build
```

This starts: `postgres`, `backend` (FastAPI on `:8000`), `frontend` (Vite dev
server on `:5173`). API docs are available at `http://localhost:8000/docs`.

## Running locally (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # DATABASE_URL etc.
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Seeding demo data

```bash
cd backend
python ../scripts/seed_demo.py
```

Populates a synthetic project so the full dashboard/simulation flow can be
demonstrated without a real GitHub token. See [`docs/demo.md`](docs/demo.md).

## Environment variables

See [`.env.example`](.env.example) — `DATABASE_URL`, `GITHUB_TOKEN`
(optional, enables PR/issue/review ingestion for GitHub repos), `LLM_PROVIDER`
+ `LLM_API_KEY` (abstraction layer, see `backend/app/ai/`).

## Roadmap

Built incrementally; each phase was tested and integrated before the next
began (master spec §44).

- [x] **Phase 1 — Project scaffolding**: monorepo layout, FastAPI skeleton, DB session/config wiring, Alembic init, Vite+React+TS+Tailwind skeleton, Docker Compose, docs.
- [x] **Phase 2 — Database models + migrations**: all 22 SQLAlchemy models in `docs/database-schema.md`, Alembic autogenerate verified.
- [x] **Phase 3 — Repository ingestion**: safe cloning + URL validation, GitPython commit/author parsing, developer identity normalization (exact-match-only auto-merge; ambiguous cases flagged, never silently merged).
- [x] **Phase 4 — Source-code analysis**: per-language analyzers (Python via `ast`; JS/TS/Java/C/C++/Go via a documented regex heuristic), directory-based module detection.
- [x] **Phase 5 — Knowledge engine**: weighted knowledge scores, HHI-based concentration.
- [x] **Phase 6 — Risk engine**: module risk with full factor breakdowns, criticality, project resilience score, knowledge drift, hidden-expert detection.
- [x] **Phase 7 — Simulation engine**: dependency graph + risk propagation (NetworkX), developer-unavailability and multi-failure "what if" simulation, backup-candidate ranking.
- [x] **Phase 8 — Recommendation engine**: rule-based, severity-ranked, knowledge-transfer plan generator.
- [x] **Phase 9 — Backend APIs**: every route in `docs/api.md` implemented and integration-tested via FastAPI's `TestClient`.
- [x] **Phase 10 — Frontend dashboard, developer/module pages**: React + TypeScript + Tailwind, builds and type-checks cleanly.
- [x] **Phase 11 — Knowledge graph page**: React Flow, developer/module filtering.
- [x] **Phase 12 — AI Project Analyst**: intent detection → grounded structured context → deterministic zero-hallucination answers by default, or a real Anthropic API call when `LLM_API_KEY` is configured.
- [x] **Phase 13 — Testing**: 22 backend tests (unit + full pipeline + full API integration) and 10 frontend tests (component, API client, routing), all passing.
- [~] **Phase 14 — Dockerization**: Dockerfiles, Compose config, and a migration-running entrypoint are in place; not build-verified in this environment (no Docker daemon available here — verify with `docker compose up --build` locally).
- [x] **Phase 15 — Documentation**: this README plus `docs/architecture.md`, `docs/database-schema.md`, `docs/api.md`, `docs/analysis-methodology.md`, `docs/risk-model.md`, `docs/demo.md`.

## Performance & incremental indexing

A later pass hardened ingestion for large repositories — see
[`docs/perf-benchmarks.md`](docs/perf-benchmarks.md) for the full measured
results. Summary:

- **Quick Scan / Full Historical Scan** modes (`?scan_mode=quick|full` on
  `POST /projects/{id}/analyze`), with bounded-depth cloning, clone
  timeouts, and disk-size/file-count budgets enforced before analysis starts.
- **Incremental indexing**: a repository's last-indexed commit is tracked
  (`Repository.last_indexed_commit_sha`), so re-analysis only fetches and
  processes commits newer than that checkpoint — measured 4-5x faster than
  a full re-scan on a 1,200-5,000 commit synthetic repo, with the gap
  widening as history grows. Force-push/rebase is detected automatically
  and falls back to a full re-scan.
- **Content-hash file caching**: unchanged source files are skipped
  entirely on re-analysis rather than re-parsed.
- **Batched Git history extraction**: a single `git log --numstat` call
  replaces per-commit GitPython diffs — measured 14.9x faster at 1,200
  commits, correctness-verified against GitPython commit-by-commit.
- **Batched DB writes**: bulk inserts replace the old per-row
  `add()`+`flush()` pattern — measured 7.4x faster at 2,000 rows on SQLite.
- **Concurrency-safe**: a partial unique index (not just an app-level check)
  prevents two analysis runs from starting on the same project at once.
- **Cooperative cancellation**: `POST /projects/{id}/analysis-runs/{run_id}/cancel`
  sets a flag the pipeline checks between stages; a cancelled run is never
  surfaced as the project's "latest" analysis.
- **Automatic module-dependency extraction** from source imports
  (`app/analyzers/module_dependency_resolver.py`) — this now populates real
  edges that drive risk propagation and the dependency-risk factor, which
  were previously always empty/zero for any freshly-analyzed repository.

See the Limitations section below for what this pass explicitly did *not*
cover (GitHub PR/issue ingestion, a Celery/RQ worker, Tree-sitter).

## Acceptance walkthrough (master spec §46–47)

With the backend and frontend running (`make up` or the manual steps above):

1. Open the app, create a project, and add a repository (a public Git URL, or run `python scripts/seed_demo.py` for the synthetic demo instead).
2. Click **Run analysis** on the Dashboard — the pipeline ingests the repo and computes every metric below from real data.
3. Dashboard shows the project resilience score, risk distribution, and top-risk modules.
4. Modules page → a module's risk score, bus factor, knowledge concentration, and full factor breakdown.
5. Knowledge Graph page → developers, modules, and their relationships, filterable.
6. Simulation page → select a developer, run "Developer Unavailable," see before/after resilience, affected modules, and ranked backup candidates.
7. Recommendations page → prioritized, severity-ranked action items citing the real metrics behind them.
8. AI Analyst → ask "Why is Payment the highest-risk module?" and get an answer grounded in the exact stored numbers.

## Limitations (see docs for detail)

Repository-derived metrics only — no informal/tribal-knowledge signal;
directory-based module detection; static-analysis complexity proxies;
simulation outputs are potential-impact estimates, not production-incident
or personnel-decision predictions.

**Performance-pass-specific, intentionally deferred** (see
`docs/perf-benchmarks.md` for what *was* done and measured):
- GitHub PR/review/issue ingestion is still not wired up (ingestion uses Git
  history only), so review/issue-based signals in the knowledge and
  hidden-expert formulas remain 0 for all repositories. This is a
  substantial separate subsystem (OAuth/token handling, pagination,
  rate-limit backoff, its own incremental-sync checkpoint) that was out of
  scope for this pass; `app/analyzers/git_history.py` and the
  `last_indexed_commit_sha` pattern it uses would be the natural model to
  extend for it.
- No Celery/RQ worker was introduced. FastAPI `BackgroundTasks` remains the
  execution model; it's documented as a scaling limitation (no retry queue,
  no cross-process worker pool). What *is* real and tested: cooperative
  cancellation (`AnalysisRun.cancel_requested`, checked between pipeline
  stages) and per-stage progress reporting — both would carry over directly
  to an RQ/Celery worker if adopted later, since neither lives in the task
  runner, both live in the pipeline itself.
- Tree-sitter was not introduced; non-Python languages still use the
  documented regex heuristic analyzer (now extended to capture import
  targets for module-dependency detection, not just counts).
- Module dependency edges ARE now auto-detected from source imports
  (`app/analyzers/module_dependency_resolver.py`) and feed real
  dependency-risk/criticality/propagation signals — this used to be
  entirely unpopulated; see `docs/perf-benchmarks.md` §4 for a worked
  example. Resolution is still heuristic (path-based matching against
  detected module prefixes), so it undercounts for unconventional import
  styles — documented as a confidence signal, not a guarantee.
- Docker Compose is configured (with a migration-running entrypoint) but
  not build-verified in this development environment (no Docker daemon
  available here).
- Quick Scan's bounded-depth clone (`--depth`) has no effect when cloning
  from a true local filesystem path — this is `git`'s own behavior
  ("--depth is ignored in local clones"), not a bug in this codebase; it
  works correctly for the `https://`/`git://` remote URLs Quick Scan is
  actually meant for, verified in testing via the `file://` transport.
