# Database ER Design (PostgreSQL, SQLAlchemy + Alembic)

All tables have `id UUID PK`, `created_at`, `updated_at` timestamps unless
noted. FKs are indexed. This is the normalized schema behind §31; the
SQLAlchemy models in `backend/app/models/` are the source of truth and
should stay in lockstep with this document.

## Core entities

```
projects
  id, name, description, risk_config JSONB (weights), created_at, updated_at

repositories
  id, project_id FK→projects, url, provider (git|github|local), default_branch,
  total_files, contributor_count, commit_count, last_analyzed_at

developers
  id, project_id FK→projects, display_name, primary_email, normalized_key

developer_aliases
  id, developer_id FK→developers, raw_name, raw_email, source (git|github),
  confidence (exact|suggested), confirmed BOOLEAN

commits
  id, repository_id FK→repositories, developer_id FK→developers, hash,
  message, authored_at, additions, deletions, files_changed_count

files
  id, repository_id FK→repositories, module_id FK→modules (nullable),
  path, language, size_bytes, is_test, is_config, doc_coverage_pct

modules
  id, repository_id FK→repositories, name, path_prefix, loc, complexity_avg,
  documentation_score, change_frequency_90d

module_dependencies
  id, module_id FK→modules, depends_on_module_id FK→modules, weight

technologies
  id, name, category (language|framework|db|infra)

developer_technologies (join)
  id, developer_id FK→developers, technology_id FK→technologies, overlap_score

pull_requests
  id, repository_id FK→repositories, author_id FK→developers, number, title,
  merged_at, files_changed (array of file ids)

reviews
  id, pull_request_id FK→pull_requests, reviewer_id FK→developers,
  submitted_at, state

issues
  id, repository_id FK→repositories, author_id FK→developers, module_id FK→modules
  (nullable), title, resolved_at

developer_file_activity
  id, developer_id FK, file_id FK, commits_count, lines_added, lines_deleted,
  last_commit_at

developer_module_activity
  id, developer_id FK, module_id FK, commits_count, lines_changed,
  reviews_count, issues_count, last_activity_at

knowledge_scores
  id, developer_id FK, module_id FK, score (0-100), component_breakdown JSONB,
  computed_at, analysis_run_id FK

risk_scores
  id, module_id FK, score (0-100), level (LOW|MODERATE|HIGH|CRITICAL),
  factors JSONB (per-factor value + weight), analysis_run_id FK, computed_at

resilience_scores
  id, project_id FK, score (0-100), label, component_breakdown JSONB,
  analysis_run_id FK, computed_at

simulations
  id, project_id FK, type (single|multiple), developer_ids (array),
  requested_at, status

simulation_results
  id, simulation_id FK, resilience_before, resilience_after,
  knowledge_impact_pct, affected_modules JSONB, backup_candidates JSONB,
  risk_propagation JSONB

recommendations
  id, project_id FK, module_id FK (nullable), severity (CRITICAL|HIGH|MODERATE),
  title, description, related_developer_id FK (nullable), analysis_run_id FK

analysis_runs
  id, project_id FK, status, stage_status JSONB (per-stage timestamps/status),
  started_at, completed_at, error_message
```

## Key relationships (crow's foot summary)

- `projects (1) ── (N) repositories`
- `repositories (1) ── (N) commits / files / modules / pull_requests / issues`
- `developers (1) ── (N) developer_aliases`
- `developers (N) ── (N) modules` via `developer_module_activity` (knowledge join)
- `modules (N) ── (N) modules` via `module_dependencies` (self-referential, directed)
- `pull_requests (1) ── (N) reviews`
- `analysis_runs (1) ── (N) knowledge_scores / risk_scores / resilience_scores / recommendations` — every derived metric is scoped to the run that produced it, so history is preserved across re-analysis (supports knowledge-drift time series without a separate snapshot table).

## Indexing strategy

- FK columns indexed by default (SQLAlchemy + Alembic autogeneration).
- `commits(repository_id, authored_at)` composite index — powers change-frequency and drift queries.
- `knowledge_scores(module_id, analysis_run_id)` and `(developer_id, analysis_run_id)` — powers both the module page and developer page without full scans.
- `developer_aliases(raw_email)` — powers identity-normalization lookups during ingestion.
