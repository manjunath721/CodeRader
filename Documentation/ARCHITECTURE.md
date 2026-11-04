# CodeRadar — System Architecture & Component Design

CodeRadar is an enterprise-grade repository intelligence and software engineering risk analysis platform.
It processes Git repositories to determine developer knowledge concentration, module risk, bus factor vulnerabilities, and architectural dependencies using deterministic algorithms and explainable rule engines.

---

## 1. High-Level Architectural Layers

The system follows a clean modular layered architecture:

```
+-------------------------------------------------------------------------+
|                              Presentation Layer                         |
|  - React 18 / TypeScript SPA                                           |
|  - Pages: Dashboard, Modules, Devs, Cosmos Graph, Simulation, Recs      |
|  - State: AuthContext (JWT session), TanStack Query / Reactive Hooks    |
+-------------------------------------------------------------------------+
                                    |
                            HTTP / REST API (JSON)
                                    |
+-------------------------------------------------------------------------+
|                                API Layer                                |
|  - FastAPI (Python 3.11) with Pydantic 2 request/response schemas        |
|  - Middleware: Security Headers, Request Correlation ID, Process Timing |
|  - Routers: /auth, /projects, /analytics, /simulations, /health         |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                             Services Layer                              |
|  - AuthService: PBKDF2-HMAC-SHA256, JWT Token Management, RBAC          |
|  - JobWorker: Mutex-locked background execution & crash recovery         |
|  - Scheduler: Background cron loop for automated project rescans         |
|  - IngestionService: Hardened Git clone, fetch, diff, pruning            |
|  - AnalysisPipeline: Multi-stage metric orchestration                    |
|  - QueryService: Aggregations, historical run diffing, and export       |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                            Analysis Engines                             |
|  - Polyglot Parsers: Python AST, Heuristic CFamily (JS/TS/Java/C/C++/Go)|
|  - Graph Analysis: NetworkX Dependency & Knowledge Graph               |
|  - Metrics Engine: Bus Factor, Criticality, Resilience Scoring (0-100)  |
|  - Recommendation Engine: Deterministic, rule-based action generation   |
+-------------------------------------------------------------------------+
                                    |
+-------------------------------------------------------------------------+
|                           Persistence Layer                             |
|  - PostgreSQL 16 Relational Database via SQLAlchemy 2 & Alembic         |
|  - Local Git Sandboxes with hook suppression & restricted protocols     |
+-------------------------------------------------------------------------+
```

---

## 2. Core Service Components

### 2.1 Authentication & RBAC Service (`app.services.auth_service`)
- **Password Security**: Standard PBKDF2-HMAC-SHA256 with 600,000 hash iterations and unique salt generation.
- **Session Tokens**: Cryptographically signed HS256 JWT tokens with configurable expiration (default 7 days).
- **Access Control Roles**:
  - `owner`: Full project administrative privileges (settings, member deletion, scan triggers, project deletion).
  - `analyst`: Can trigger manual rescans, run simulations, export reports, and adjust risk weights.
  - `viewer`: Read-only access to metrics, dashboards, and graphs.
- **Audit Logging**: Every sensitive action (login, member updates, scan trigger, scan cancellation) records an immutable event in the `audit_logs` table.

### 2.2 Background Job Worker & Concurrency Control (`app.services.job_worker`)
- **Mutual Exclusion**: Per-project concurrency locks ensure two analysis runs cannot execute concurrently on the same project.
- **Crash Recovery**: `recover_stale_runs_on_startup()` inspects `analysis_runs` upon API server boot, automatically marking orphaned `running` or `pending` runs as `failed` with diagnostic logs.
- **Graceful Cancellation**: Analysis stages periodically verify `cancel_requested` flags. When a cancellation is detected, previous Git checkpoints are restored, and resources are cleanly freed.

### 2.3 Rescan & Reconciliation Engine (`app.services.ingestion_service` & `analysis_pipeline`)
- **Safe Clone & Fetch**:
  - `-c core.hooksPath=/dev/null` blocks malicious hook execution on clone/checkout.
  - `-c protocol.file.allow=never` prevents local file protocol escalation and symlink attacks.
- **Commit Checkpointing**: The repository `last_indexed_commit_sha` is updated **only** upon successful completion of all pipeline stages. If an ingestion or calculation fails, the checkpoint remains at the prior stable SHA.
- **Tree Reconciliation**: Identifies deleted upstream files, removes stale `File` records, and safely cascades pruning to empty modules and obsolete dependency edges.
- **Execution Limits**: Enforces `MAX_COMMITS_PER_RUN` (default: 50,000) and timeouts on subprocess Git commands.

### 2.4 Polyglot Source Analyzers (`app.analyzers.source`)
- **Python**: Native `ast` module parsing for exact imports, class declarations, and function complexity.
- **CFamily Analyzer**: Regex and heuristic lexing for JavaScript/TypeScript (`import`, `require`), Java (`import package.class;`), C/C++ (`#include`), and Go (`import`).
- **Graph Cycle Detection**: Evaluates circular dependencies using NetworkX `simple_cycles` and computes degree centrality.

### 2.5 Deterministic Recommendation Engine (`app.recommendations.engine`)
- Replaces black-box AI with transparent, explainable rule trees.
- Every recommendation outputs a specific `rule_type`, `triggering_metric`, severity, and concrete `suggested_action`.
- Produces standardized 6-part knowledge transfer plans for high-risk single-maintainer modules.

---

## 3. Communication Protocols & Data Contracts

- **RESTful JSON**: All API communication adheres to standard HTTP status codes:
  - `200 OK`: Successful query or update.
  - `201 Created`: Successful entity creation.
  - `400 Bad Request`: Schema validation failure or invalid parameter.
  - `401 Unauthorized`: Missing or invalid JWT Bearer token.
  - `403 Forbidden`: Insufficient role or unauthorized project access.
  - `404 Not Found`: Resource does not exist.
  - `409 Conflict`: Concurrency conflict (analysis run already running).
- **Security Headers**: Injected on all HTTP responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- **Request Correlation**: The `X-Request-ID` header is propagated across all log entries and returned to clients for end-to-end debugging.
