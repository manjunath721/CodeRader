# CodeRadar — System Architecture

## 1. Overview

CodeRadar converts raw Git/GitHub activity into an explainable model of
**software-team knowledge risk**. It is not a productivity tracker: every
number it produces is a *repository-derived estimate*, clearly labeled as
such, and traceable back to the underlying commits/files/reviews that
produced it.

The system is a monorepo with three deployable units:

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌──────────────────┐
│   Frontend (Vite)    │ ───► │   Backend (FastAPI)       │ ───► │   PostgreSQL      │
│   React + TS         │ ◄─── │   REST API + Worker        │ ◄─── │   (SQLAlchemy)    │
└─────────────────────┘      └──────────────────────────┘      └──────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ Analysis Pipeline │  (GitPython, NetworkX,
                              │ (background job)  │   pandas, scikit-learn)
                              └─────────────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  LLM Provider     │  (abstraction layer,
                              │  Abstraction      │   structured-context only)
                              └─────────────────┘
```

## 2. Backend module responsibilities

| Package | Responsibility |
|---|---|
| `app/api` | FastAPI routers — thin, no business logic. Validate → call service → serialize. |
| `app/core` | Config, DB session, security, logging, background-task orchestration. |
| `app/models` | SQLAlchemy ORM models (one file per aggregate: project, developer, module, ...). |
| `app/schemas` | Pydantic request/response schemas, decoupled from ORM models. |
| `app/services` | Application/business logic that orchestrates repositories + analyzers. Called by API layer. |
| `app/analyzers` | Repository ingestion, source-code parsing, module/technology detection. Pure functions where possible, operate on a cloned repo path. |
| `app/graph` | Knowledge graph construction (NetworkX) and graph queries. |
| `app/risk` | Knowledge scoring, concentration (HHI), bus factor, criticality, risk engine, resilience score, knowledge drift, hidden-expert detection. |
| `app/simulation` | "What if" developer-unavailability and multi-failure simulation engine, risk propagation over the module-dependency graph. |
| `app/recommendations` | Backup-developer ranking, knowledge-transfer plan generation, prioritized recommendation list. |
| `app/ai` | LLM provider abstraction + AI Project Analyst (intent detection → structured context retrieval → grounded prompt → answer). |

## 3. Analysis pipeline (background job)

The pipeline in `POST /api/projects/{id}/analyze` runs as an async background
task (FastAPI `BackgroundTasks` for MVP; documented upgrade path to
Celery/RQ + Redis for production scale — see §7). It executes the ordered
stages from the master spec (§33), persisting an `analysis_runs` row that
tracks per-stage status so the frontend can render a live progress list:

1. Repository validation
2. Clone repository (shallow, to a scratch dir, deleted after ingestion)
3. Parse Git history (GitPython) → commits, diffs, authors
4. Normalize developer identities (configurable alias rules, never silent auto-merge of ambiguous identities)
5. Analyze source files (per-language analyzers, see §6)
6. Detect modules (directory-based heuristic, configurable depth)
7. Detect technologies (import/dependency-manifest based)
8. Calculate developer↔file and developer↔module activity aggregates
9. Calculate knowledge scores (per developer/module pair)
10. Build knowledge graph (NetworkX, cached to DB as edge/node tables for the frontend)
11. Calculate bus factor (per module, per project, per critical module)
12. Calculate module risk scores (weighted, explainable)
13. Calculate project resilience score
14. Detect knowledge drift (time-bucketed knowledge-score history)
15. Detect hidden experts (multi-signal secondary-expertise scoring)
16. Generate recommendations (rule-based, ranked by severity)
17. Store results, mark `analysis_runs.status = 'complete'`

Each stage writes its own timestamped status so a failure at stage 9 doesn't
report the whole run as an opaque failure — the frontend shows exactly which
stage failed and the operator-facing error message from §43.

## 4. Data flow guarantee

Every dashboard number is read from a database row written by a pipeline
stage above. The frontend never computes a metric itself, and the AI layer
never invents one — see `docs/analysis-methodology.md` and `docs/risk-model.md`
for the exact formulas, and §24/§42 of the master spec for the AI grounding
contract.

## 5. Frontend structure

```
frontend/src/
  pages/        Dashboard, ProjectSetup, DeveloperPage, ModulePage,
                 KnowledgeGraphPage, SimulationPage, RecommendationsPage,
                 AIAnalystChat
  components/    Reusable risk badges, charts (Recharts), graph canvas
                 (React Flow / D3), progress trackers, tables
  services/      Typed API client (fetch wrapper + TanStack Query hooks)
  types/         TypeScript types mirrored from backend Pydantic schemas
  hooks/         useProject, useSimulation, useKnowledgeGraph, etc.
```

Frontend and backend types are kept in sync by generating TypeScript types
from the FastAPI OpenAPI schema (`openapi-typescript`) as a build step —
avoids hand-duplicated, drifting type definitions.

## 6. Language-aware source analysis

`app/analyzers/source/` defines one analyzer per language behind a common
`LanguageAnalyzer` interface (`parse(file_text) -> FileFacts`), initially:
Python (via `ast`), JavaScript/TypeScript (regex + heuristic AST-lite parser
to avoid a heavy JS toolchain dependency in the Python backend), Java, C/C++,
Go (heuristic regex-based extraction of functions/classes/imports/complexity
proxies for non-Python languages in the MVP, upgradeable to tree-sitter later).
Adding a language means implementing one interface and registering it in
`app/analyzers/source/registry.py` — no changes elsewhere.

## 7. Scalability notes (MVP limitations, documented per §34/§40)

- MVP target: 10–100 developers, thousands–tens of thousands of commits, thousands of files.
- Background jobs run in-process (FastAPI `BackgroundTasks`) for the MVP; this
  is a documented limitation — production deployments should move to a real
  task queue (Celery/RQ + Redis) for concurrency and retry semantics.
- Incremental analysis (only new commits since the last `analysis_runs`)
  is a documented Phase-2+ enhancement; MVP re-analyzes the full history on
  each run but caches per-file parse results keyed by blob hash.
- Knowledge graph is persisted as node/edge tables so the frontend graph page
  loads from Postgres rather than recomputing NetworkX on every request.

## 8. Security posture (§35)

- No secrets in the frontend bundle; GitHub tokens live server-side only,
  read from environment variables via `app/core/config.py`.
- Repository URLs are validated against an allow-list of schemes
  (`https://`, `git://`) and hostnames are checked before `git clone`.
- Cloning uses `GitPython` with `depth` limits and a subprocess timeout;
  no shell=True, no string-interpolated subprocess commands.
- Source analysis is static only — cloned repository code is never executed.
- AI prompts are built from structured, escaped context blocks — user input
  reaching the LLM is treated as untrusted and never used to build tool/API
  calls directly.
