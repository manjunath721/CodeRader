# CodeRadar — REST API Specification

Base URL: `/api`

All API endpoints accept and return JSON payloads unless otherwise specified.
Protected endpoints require an `Authorization: Bearer <JWT_TOKEN>` header.

---

## 1. Authentication & Identity (`/auth`)

### `POST /auth/register`
Creates a new user account.
- **Request Body**:
  ```json
  {
    "email": "engineer@example.com",
    "password": "SecurePassword123!",
    "full_name": "Jane Engineer"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1Ni...",
    "token_type": "bearer",
    "user": {
      "id": "c3d4e5f6-...",
      "email": "engineer@example.com",
      "full_name": "Jane Engineer",
      "role": "analyst",
      "is_active": true,
      "created_at": "2026-11-04T12:00:00Z"
    }
  }
  ```

### `POST /auth/login`
Authenticates with email and password.
- **Request Body**:
  ```json
  {
    "email": "engineer@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response `200 OK`**: Same token structure as register.

### `GET /auth/me`
Retrieves the currently authenticated user profile. Requires Bearer Token.

---

## 2. Project Management (`/projects`)

### `GET /projects`
Lists all accessible projects.

### `POST /projects`
Creates a new project.
- **Request Body**:
  ```json
  {
    "name": "Platform Core",
    "description": "Core distributed backend services",
    "risk_config": {
      "risk_weights": {
        "knowledge_concentration": 0.30,
        "bus_factor_risk": 0.25,
        "documentation_risk": 0.15,
        "complexity_risk": 0.15,
        "change_frequency_risk": 0.08,
        "dependency_risk": 0.07
      },
      "criticality_threshold": 65.0,
      "bus_factor_threshold": 2,
      "recency_half_life_days": 90
    }
  }
  ```

### `GET /projects/{project_id}`
Retrieves detailed metadata for a project.

### `DELETE /projects/{project_id}`
Deletes a project and cascades deletion to all associated repositories, modules, and analysis runs. Requires `owner` role.

### `POST /projects/{project_id}/repositories`
Attaches a Git repository to a project.
- **Request Body**:
  ```json
  {
    "url": "https://github.com/org/repo.git",
    "provider": "github"
  }
  ```

---

## 3. Analysis & Rescan Execution

### `POST /projects/{project_id}/analyze`
Enqueues a new analysis or rescan background task.
- **Query Parameters**:
  - `scan_mode`: `full` | `quick` (Default: `full`)
  - `rescan_type`: `manual` | `scheduled` | `quick` | `incremental` (Default: `manual`)
- **Request Body** (Optional):
  ```json
  {
    "scan_mode": "full",
    "force_full_rescan": false
  }
  ```
- **Response `200 OK`**:
  Returns the initial `AnalysisRun` record with status `pending`.
- **Response `409 Conflict`**: Returned if an analysis is already in progress for this project.

### `GET /projects/{project_id}/analysis-runs`
Lists all historical analysis runs for this project.

### `GET /projects/{project_id}/analysis-runs/{run_id}`
Polls progress, stages, and completion state of a specific run.

### `POST /projects/{project_id}/analysis-runs/{run_id}/cancel`
Requests graceful cancellation of an active analysis run. Restores prior stable Git commit checkpoint.

### `GET /projects/{project_id}/analysis-runs/{base_run_id}/compare/{target_run_id}`
Computes delta metrics between two historical snapshots:
- Resilience score before vs after
- Module-by-module risk score shifts
- Newly introduced high-risk modules
- Resolved risk areas

### `GET /projects/{project_id}/analysis-runs/{run_id}/export`
Exports complete analysis dataset.
- **Query Parameters**:
  - `format`: `json` | `csv` (Default: `json`)
- Returns downloadable `.json` report or `.csv` tabular breakdown.

---

## 4. Project Configuration & Access Control

### `GET /projects/{project_id}/risk-config`
Retrieves current risk scoring weights and thresholds.

### `PATCH /projects/{project_id}/risk-config`
Updates risk scoring weights and thresholds. Requires `owner` or `analyst` role.

### `PATCH /projects/{project_id}/schedule`
Configures background rescan cron interval.
- **Query Parameter**:
  - `interval_hours`: `0` (disabled), `24` (daily), `168` (weekly). Requires `owner` role.

### `GET /projects/{project_id}/members`
Lists assigned project team members and their roles.

### `POST /projects/{project_id}/members`
Assigns a user to a project with a specific role (`owner`, `analyst`, `viewer`). Requires `owner` role.

### `DELETE /projects/{project_id}/members/{user_id}`
Revokes a user's membership from the project. Requires `owner` role.

### `GET /projects/{project_id}/audit-logs`
Returns the immutable audit trail of actions taken within the project.

---

## 5. Analytics & Graph

### `GET /projects/{project_id}/dashboard`
Aggregated dashboard metrics: resilience score, developer count, module count, risk distribution, top risk modules, and critical knowledge areas.

### `GET /projects/{project_id}/knowledge-graph`
Returns nodes (developers, modules) and edges (ownership shares, dependency calls) for Cosmos visualization.

### `GET /projects/{project_id}/recommendations`
Returns prioritized, explainable rule-based recommendations.

### `POST /projects/{project_id}/knowledge-transfer-plan`
Generates a structured knowledge transfer curriculum.
- **Request Body**:
  ```json
  {
    "module_name": "backend/app/auth",
    "backup_developer_id": "d1e2f3a4-...",
    "priority": "HIGH"
  }
  ```

### `POST /simulations/developer-unavailability`
Simulates the organizational and architectural impact if one or more developers depart.
- **Request Body**:
  ```json
  {
    "project_id": "p1e2f3a4-...",
    "developer_ids": ["d1e2f3a4-...", "d2e3f4a5-..."]
  }
  ```

---

## 6. Health & Diagnostics (`/health`)

- `GET /health`: Basic service status.
- `GET /health/live`: Liveness probe for Kubernetes / Docker.
- `GET /health/ready`: Readiness probe verifying PostgreSQL database connectivity.
