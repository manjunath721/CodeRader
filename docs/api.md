# API Specification (v1)

Base path: `/api`. All responses are JSON. Errors follow:
```json
{ "detail": "human-readable message", "code": "REPO_NOT_ACCESSIBLE" }
```
(see §43 for the canonical error message catalog, implemented in
`app/core/errors.py`).

## Projects & Repositories

| Method | Path | Description |
|---|---|---|
| POST | `/projects` | Create a project |
| GET | `/projects` | List projects |
| GET | `/projects/{id}` | Get project detail |
| POST | `/projects/{id}/repositories` | Attach a Git/GitHub repository to a project |
| POST | `/projects/{id}/analyze` | Kick off analysis pipeline (background job); returns `analysis_run_id` |
| GET | `/projects/{id}/analysis-runs/{run_id}` | Poll pipeline stage status |

## Dashboard & core metrics

| Method | Path | Description |
|---|---|---|
| GET | `/projects/{id}/dashboard` | Aggregated dashboard payload (resilience, risk distribution, top-risk modules, drift, critical areas) |
| GET | `/projects/{id}/developers` | List developers with summary knowledge/dependency stats |
| GET | `/projects/{id}/modules` | List modules with risk/resilience/bus-factor summary |
| GET | `/projects/{id}/knowledge-graph` | Graph nodes/edges (filterable via query params: `developer_id`, `module_id`, `technology`) |
| GET | `/projects/{id}/files` | Per-file inventory (`?limit=`, ordered by complexity) — powers the Cosmos file layer |
| GET | `/projects/{id}/libraries` | Third-party packages derived from captured source imports — powers the Cosmos library diamonds |
| GET | `/projects/{id}/risks` | Full risk breakdown per module, each with a `factors` explanation object |
| GET | `/projects/{id}/resilience` | Resilience score + component breakdown + history |
| GET | `/projects/{id}/knowledge-drift` | Time-series concentration data per module |
| GET | `/projects/{id}/recommendations` | Prioritized recommendation list |

## Developer / Module detail

| Method | Path | Description |
|---|---|---|
| GET | `/developers/{id}` | Profile, knowledge areas, modules, technologies, timeline, critical ownership, dependency risk |
| GET | `/modules/{id}` | Risk, resilience, bus factor, distribution, documentation, complexity, dependencies, backup candidates, historical risk |

## Simulation

| Method | Path | Description |
|---|---|---|
| POST | `/simulations/developer-unavailability` | Body: `{project_id, developer_id}` → before/after resilience, affected modules, backup candidates, risk-propagation tree |
| POST | `/simulations/multiple-failure` | Body: `{project_id, developer_ids[]}` → same shape, multi-developer |
| GET | `/simulations/{id}` | Retrieve a stored simulation result |
| GET | `/projects/{id}/simulations` | Simulation history for comparison |

## Demo workspace

| Method | Path | Description |
|---|---|---|
| POST | `/demo/ensure` | Idempotent demo bootstrap → `{project_id, analysis_run_id, status, created}`. Returns the existing fully-analyzed demo project when available, otherwise builds + analyzes a fresh one. Powers the frontend's one-click "Load demo workspace" button. |

## AI Analyst

| Method | Path | Description |
|---|---|---|
| POST | `/ai/query` | Body: `{project_id, question}`. Pipeline: intent detection → metric retrieval → structured context → LLM → grounded answer. Response includes the `context` used, so the UI can show "based on these metrics" alongside the answer. |

## Conventions

- Pagination: `?page=&page_size=` on list endpoints, response envelope `{items, total, page, page_size}`.
- All numeric metrics are returned alongside their explanation object — no bare scores are ever returned without the contributing factors, per the explainability requirement (§40, §42).
- All IDs are UUIDs.
- Auth: not required for the local-first MVP demo; `app/core/security.py` stubs a bearer-token dependency so multi-user auth can be added in Phase 2+ without route changes.
