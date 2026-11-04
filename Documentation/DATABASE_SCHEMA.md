# CodeRadar — Database Schema & Data Dictionary

CodeRadar utilizes PostgreSQL 16 as its primary relational store. Database schema migrations are strictly version-controlled using Alembic.

---

## 1. Schema Migration History

| Version Hash | Date | Description | Status |
|---|---|---|---|
| `e0a1f2b3c4d5` | Initial | Initial database schema (projects, repositories, files, commits, authors, modules, knowledge_scores, risk_scores, analysis_runs) | Applied |
| `f1b2c3d4e5f6` | Follow-up | Performance indexes and repository metadata columns | Applied |
| `d4e1f56a7890` | Release 2.0 | Added `users`, `project_members`, `audit_logs`, `rescan_interval_hours`, `rescan_type`, `commit_sha`, and `lines_of_code` | Applied |

All migrations are fully reversible and verified via offline SQL generation (`alembic upgrade head --sql`).

---

## 2. Table Specifications

### 2.1 `users`
Stores user identities and authentication credentials.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key | Unique user identifier |
| `email` | `VARCHAR(255)` | Unique, Indexed, NOT NULL | User email address |
| `hashed_password` | `VARCHAR(255)` | NOT NULL | PBKDF2-HMAC-SHA256 password hash |
| `full_name` | `VARCHAR(255)` | Nullable | User display name |
| `role` | `VARCHAR(50)` | NOT NULL, Default: `'analyst'` | Global role (`admin`, `analyst`, `viewer`) |
| `is_active` | `BOOLEAN` | NOT NULL, Default: `TRUE` | Account active status |
| `created_at` | `TIMESTAMP` | NOT NULL | Record creation timestamp |
| `updated_at` | `TIMESTAMP` | NOT NULL | Last update timestamp |

### 2.2 `project_members`
Implements project-level Role-Based Access Control (RBAC).

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key | Unique membership record ID |
| `project_id` | `UUID` | Foreign Key (`projects.id`, ON DELETE CASCADE), Indexed | Associated project ID |
| `user_id` | `UUID` | Foreign Key (`users.id`, ON DELETE CASCADE), Indexed | Associated user ID |
| `role` | `VARCHAR(50)` | NOT NULL, Default: `'analyst'` | Project role (`owner`, `analyst`, `viewer`) |
| `created_at` | `TIMESTAMP` | NOT NULL | Membership grant timestamp |

### 2.3 `audit_logs`
Immutable audit trail for compliance and security events.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key | Unique audit log ID |
| `actor_id` | `UUID` | Foreign Key (`users.id`, ON DELETE SET NULL), Nullable | Actor user ID |
| `actor_email` | `VARCHAR(255)` | Nullable | Snapshot of actor email |
| `action` | `VARCHAR(100)` | NOT NULL, Indexed | Action name (e.g. `start_rescan`, `update_settings`) |
| `resource_type` | `VARCHAR(50)` | NOT NULL | Target entity type (e.g. `project`, `user`) |
| `resource_id` | `VARCHAR(100)` | Nullable | Target entity ID |
| `details` | `JSONB / JSON` | NOT NULL, Default: `{}` | Action metadata payload |
| `ip_address` | `VARCHAR(50)` | Nullable | Request client IP address |
| `created_at` | `TIMESTAMP` | NOT NULL, Indexed | Event timestamp |

### 2.4 `projects`
Root organizational container for repositories and analysis runs.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key | Unique project ID |
| `name` | `VARCHAR(255)` | NOT NULL | Project name |
| `description` | `TEXT` | Nullable | Project description |
| `is_demo` | `BOOLEAN` | NOT NULL, Default: `FALSE` | Synthetic demo flag |
| `risk_config` | `JSONB / JSON` | Nullable | Custom risk weights & thresholds |
| `rescan_interval_hours` | `INTEGER` | NOT NULL, Default: `0` | Rescan schedule (0=disabled, 24=daily, 168=weekly) |
| `created_at` | `TIMESTAMP` | NOT NULL | Creation timestamp |

### 2.5 `repositories`
Tracks Git repositories linked to a project.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key | Unique repository ID |
| `project_id` | `UUID` | Foreign Key (`projects.id`, ON DELETE CASCADE), Indexed | Parent project ID |
| `url` | `VARCHAR(500)` | NOT NULL | Git repository remote URL or local path |
| `provider` | `VARCHAR(50)` | NOT NULL, Default: `'git'` | Host provider (`git`, `github`) |
| `last_indexed_commit_sha`| `VARCHAR(40)`| Nullable | Last successfully completed commit SHA checkpoint |
| `local_path` | `VARCHAR(500)` | Nullable | Local working directory cache path |

### 2.6 `analysis_runs`
Records historical snapshots of repository analysis executions.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary Key | Unique run execution ID |
| `project_id` | `UUID` | Foreign Key (`projects.id`, ON DELETE CASCADE), Indexed | Parent project ID |
| `status` | `VARCHAR(50)` | NOT NULL | `pending`, `running`, `complete`, `failed`, `cancelled` |
| `scan_mode` | `VARCHAR(20)` | NOT NULL | `quick`, `full` |
| `rescan_type` | `VARCHAR(50)` | NOT NULL, Default: `'manual'` | `manual`, `scheduled`, `quick`, `incremental` |
| `commit_sha` | `VARCHAR(40)` | Nullable | Git HEAD commit SHA analyzed during this run |
| `cancel_requested` | `BOOLEAN` | NOT NULL, Default: `FALSE` | Signal flag for graceful task abort |
| `stage_status` | `JSONB / JSON` | NOT NULL | Status per pipeline stage |
| `progress` | `JSONB / JSON` | NOT NULL | Detailed ingestion and parsing progress counters |
| `started_at` | `TIMESTAMP` | Nullable | Execution start timestamp |
| `completed_at` | `TIMESTAMP` | Nullable | Execution finish timestamp |
| `error_message` | `TEXT` | Nullable | Failure stack summary if status is `failed` |

### 2.7 `modules` & `files`
Tracks code structure, directories, and files.

| Table | Key Columns | Description |
|---|---|---|
| `modules` | `id`, `repository_id`, `name`, `path_prefix`, `loc` | Logical architectural module groupings |
| `files` | `id`, `repository_id`, `module_id`, `path`, `language`, `lines_of_code` | Individual source code files |
| `module_dependencies` | `id`, `source_module_id`, `target_module_id`, `strength` | Directed dependency edges between modules |

### 2.8 Metrics & Scores
- `knowledge_scores`: Developer-to-module knowledge shares, commit counts, lines authored, and recency scores.
- `risk_scores`: Module-level multi-factor risk scores, bus factor, concentration %, complexity, and criticality.
- `resilience_scores`: Aggregate repository resilience score (0-100) and component breakdown.
- `recommendations`: Action items produced by the deterministic recommendation engine.
