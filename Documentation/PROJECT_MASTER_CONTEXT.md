# CodeRadar — Project Master Context & Architecture Reference

## 1. Project Purpose & Positioning

CodeRadar is a repository intelligence and software engineering risk analysis platform.
It analyzes Git commit history and source code trees to estimate:
- Developer knowledge concentration
- Developer-to-module ownership
- Software module risk & criticality
- Bus factor (single points of failure)
- Architectural dependencies & circular references
- System resilience (0 to 100)
- Developer unavailability impact & succession planning
- Rule-based risk recommendations
- Historical run comparisons and metric drift

**Strict Engineering Boundary**: CodeRadar is **not** an employee productivity tracker or performance evaluation system. Observable Git history is merely an engineering proxy for module familiarity and architectural risk.

---

## 2. Zero AI / ML Guarantee

In accordance with architectural requirements, all AI, LLM, and non-deterministic ML components have been completely eliminated:
- No external LLM providers (Anthropic, Gemini, OpenAI).
- No API keys or external inference network calls.
- No non-deterministic text generation.
- Replaced entirely with deterministic, explainable algorithms, polyglot static parsing, graph theory (NetworkX), and rule-based decision trees.
- Every emitted recommendation includes its exact triggering metric, threshold rule, affected module or engineer, and concrete suggested actions.

---

## 3. Technology Stack

- **Frontend**: React 18, TypeScript, Vite, React Router, Tailwind CSS, React Flow, Lucide Icons
- **Backend**: Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic
- **Database**: PostgreSQL 16 (production), SQLite in-memory (isolated test runs)
- **Security**: PBKDF2-HMAC-SHA256 (600,000 iterations), PyJWT, security headers, SSRF protections
- **Infrastructure**: Docker, Docker Compose, GitHub Actions CI workflow

---

## 4. Architectural Summary

1. **Authentication & RBAC (`app.services.auth_service`)**:
   - Cryptographic PBKDF2 password hashing with unique per-user salts.
   - HS256 JWT bearer token issuance and signature verification.
   - Three-tier project role system: `owner`, `analyst`, `viewer`.
   - Immutable audit logging of all sensitive operations in `audit_logs`.
2. **Background Analysis & Concurrency (`app.services.job_worker`)**:
   - Thread pool execution decoupled from HTTP request loops.
   - Per-project in-memory mutual exclusion mutexes preventing race conditions.
   - Boot-time crash recovery (`recover_stale_runs_on_startup()`) marking orphaned runs as failed.
3. **Rescan & Synchronization (`app.services.ingestion_service` & `analysis_pipeline`)**:
   - Full, Incremental, Quick, and Scheduled rescan modes.
   - Safe Git cloning with `-c core.hooksPath=/dev/null` and `-c protocol.file.allow=never`.
   - Commit SHA checkpoints updated **only** upon full pipeline success; restored on failure or cancellation.
   - Safe deletion reconciliation and empty module pruning.
4. **Polyglot Source Parsing (`app.analyzers.source`)**:
   - Python AST analysis for imports, classes, and cyclomatic complexity.
   - CFamily analyzer for JavaScript, TypeScript, Java (`import package.class;`), C, C++, and Go.
   - Cycle detection and degree centrality via NetworkX.
5. **Deterministic Recommendation Engine (`app.recommendations.engine`)**:
   - Rule-based action items covering low bus factor, high concentration, missing documentation, high complexity, churn hotspots, and architectural bottlenecks.
   - Standardized 6-topic knowledge transfer curriculums for succession planning.

---

## 5. Verification Status

- Backend Pytest: **57 passed, 0 failed**
- Frontend Vitest: **11 passed, 0 failed**
- Frontend Build: **Passed** (`tsc -b && vite build`)
- Frontend ESLint: **Passed** (0 errors, 0 warnings)
- Alembic Offline Migration Check: **Passed** (`alembic upgrade head --sql`)
