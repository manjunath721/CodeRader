# CodeRadar — Architectural Diagrams and Workflows

This document contains 20 comprehensive Mermaid diagrams depicting the end-to-end architecture, data flows, operational cycles, and algorithmic state machines of CodeRadar.

---

## 1. System Architecture

```mermaid
flowchart TD
    Client["Client Browsers (SPA / Desktop)"]
    ViteNginx["Frontend Layer (React 18 / Vite / Nginx)"]
    FastAPI["Backend API Layer (FastAPI / Pydantic 2)"]
    
    subgraph CoreServices ["Core Application Services"]
        AuthSvc["Auth & RBAC Service (PBKDF2 / JWT)"]
        IngestSvc["Git Ingestion Engine (Hardened Git CLI)"]
        AnalysisSvc["Deterministic Analysis Pipeline"]
        WorkerPool["Background Worker Pool & Job Locks"]
        Scheduler["Rescan Cron Scheduler"]
        QuerySvc["Analytics & Diff Query Service"]
    end
    
    subgraph AnalysisEngines ["Analysis & Metrics Engines"]
        ASTParser["Polyglot AST & Import Parsers"]
        GraphEngine["Dependency & Knowledge Graph (NetworkX)"]
        ScoringEngine["Risk & Criticality Scoring Engine"]
        ResilienceEngine["Resilience & Simulation Engine"]
        RuleEngine["Deterministic Recommendation Engine"]
    end

    subgraph DataStorage ["Data & Storage Layer"]
        Postgres[(PostgreSQL 16 Relational DB)]
        GitCache[("Local Git Repositories Cache / Sandboxes")]
    end

    Client -->|HTTPS / REST| ViteNginx
    ViteNginx -->|Reverse Proxy /api| FastAPI
    FastAPI --> AuthSvc
    FastAPI --> QuerySvc
    FastAPI --> WorkerPool
    WorkerPool --> IngestSvc
    WorkerPool --> AnalysisSvc
    Scheduler -->|Trigger Periodic Rescan| WorkerPool
    IngestSvc --> GitCache
    AnalysisSvc --> ASTParser
    AnalysisSvc --> GraphEngine
    AnalysisSvc --> ScoringEngine
    AnalysisSvc --> ResilienceEngine
    AnalysisSvc --> RuleEngine
    AuthSvc --> Postgres
    QuerySvc --> Postgres
    AnalysisSvc --> Postgres
```

---

## 2. Frontend / Backend / Database Architecture

```mermaid
flowchart LR
    subgraph Frontend ["Frontend (React 18 + TypeScript)"]
        UI_Pages["Pages: Dashboard, Modules, Devs, Sim, Recs, History, Settings"]
        UI_Context["AuthContext (JWT Session & State)"]
        UI_API["Typed API Client (Fetch + Error Normalizer)"]
    end

    subgraph Backend ["Backend (FastAPI + SQLAlchemy 2)"]
        API_Routers["Routers: /auth, /projects, /analytics, /simulations, /health"]
        Middlewares["Security Headers + Request Correlation + Timing"]
        Auth_Guard["RBAC Guards (owner, analyst, viewer)"]
        Workers["Async Thread Worker Pool & Concurrency Locks"]
    end

    subgraph Database ["Database (PostgreSQL 16)"]
        Auth_Tables[("users, project_members, audit_logs")]
        Core_Tables[("projects, repositories, files, modules")]
        Metrics_Tables[("commits, authors, knowledge_scores, risk_scores")]
        Analysis_Tables[("analysis_runs, resilience_scores, recommendations")]
    end

    UI_Pages --> UI_Context
    UI_Pages --> UI_API
    UI_API -->|JSON over HTTP| API_Routers
    API_Routers --> Middlewares
    Middlewares --> Auth_Guard
    Auth_Guard --> Workers
    Workers --> Database
    API_Routers --> Database
```

---

## 3. Repository Ingestion Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI Projects API
    participant Worker as Background Worker
    participant Git as Hardened Git CLI
    participant DB as PostgreSQL Database

    User->>API: Add Repository (URL, Provider)
    API->>DB: Store Repository Record (status: pending)
    API-->>User: Repository Created
    User->>API: Start Analysis (mode: full/incremental/quick)
    API->>Worker: Enqueue Task with Project Lock
    Worker->>Git: Clone or Fetch (-c core.hooksPath=/dev/null -c protocol.file.allow=never)
    Git-->>Worker: Repository Mirror Ready
    Worker->>Git: Inspect Tree & Extract Commits / Diff Logs
    Git-->>Worker: Commit & File Metadata
    Worker->>DB: Batch Insert Files, Authors, Commits (Bounded by MAX_COMMITS_PER_RUN)
    Worker->>DB: Prune Deleted Upstream Files & Empty Modules
    Worker-->>API: Ingestion Stage Completed
```

---

## 4. Git Analysis Pipeline

```mermaid
flowchart TD
    Start([Start Pipeline]) --> Ingest[Stage 1: Repository Ingestion & Safe Clone]
    Ingest --> Commits[Stage 2: Commit History & LOC Extraction]
    Commits --> SourceParse[Stage 3: Polyglot AST Parsing - JS/TS/Java/C/C++/Go]
    SourceParse --> DepGraph[Stage 4: Architectural Module Dependency Graph]
    DepGraph --> Knowledge[Stage 5: Developer Knowledge & Recency Scoring]
    Knowledge --> RiskCompute[Stage 6: Multi-Factor Risk & Bus Factor Calculation]
    RiskCompute --> Resilience[Stage 7: System Resilience Scoring 0-100]
    Resilience --> RuleRecs[Stage 8: Deterministic Rule-Based Recommendations]
    RuleRecs --> Checkpoint[Update Repository Commit SHA Checkpoint]
    Checkpoint --> Done([Analysis Complete & Persisted])
```

---

## 5. Repository Rescan Workflow

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> IngestionRequested: Trigger Rescan (Manual / Scheduled)
    IngestionRequested --> ConcurrencyCheck: Acquire Project Mutex
    ConcurrencyCheck --> BusyRejected: Project Already Running
    ConcurrencyCheck --> FetchOrigin: Mutex Acquired
    FetchOrigin --> GitReconcile: Git Fetch & Head Evaluation
    GitReconcile --> DetectChanges: Compare with last_indexed_commit_sha
    DetectChanges --> IncrementalIngest: New Commits Found
    DetectChanges --> FullReindex: Full Rescan Forced / Rebase Detected
    IncrementalIngest --> ExecuteStages: Ingest Delta Commits & Files
    FullReindex --> ExecuteStages: Ingest Bounded Full History
    ExecuteStages --> UpdateCheckpoint: All Stages Succeeded
    ExecuteStages --> RollbackCheckpoint: Error / Stage Failure
    UpdateCheckpoint --> ReleaseLock: Persist New Checkpoint SHA
    RollbackCheckpoint --> ReleaseLock: Retain Prior Stable SHA
    ReleaseLock --> Idle
```

---

## 6. Incremental versus Full Rescan Workflow

```mermaid
flowchart TD
    Trigger([Rescan Initiated]) --> ModeCheck{Rescan Type?}
    
    ModeCheck -->|Incremental| CheckSHA[Read Repo last_indexed_commit_sha]
    ModeCheck -->|Quick| DepthLimit[Bound Git Log to Depth N commits]
    ModeCheck -->|Full| ResetCheckpoint[Ignore Previous Commit Checkpoint]

    CheckSHA --> GitRevList[Run git rev-list base_sha..HEAD]
    GitRevList --> HasNewCommits{New Commits?}
    HasNewCommits -->|Yes| IngestNew[Ingest only newly arrived commits & changed files]
    HasNewCommits -->|No| FastForward[Reuse cached commit records & update metrics]

    DepthLimit --> IngestRecent[Ingest top 500 recent commits only]
    ResetCheckpoint --> FullIngest[Ingest complete historical log up to MAX_COMMITS_PER_RUN]

    IngestNew --> ReconcileFiles[Reconcile deleted files and prune empty modules]
    FastForward --> ReconcileFiles
    IngestRecent --> ReconcileFiles
    FullIngest --> ReconcileFiles

    ReconcileFiles --> ComputeKnowledge[Recalculate Knowledge & Risk Scores]
```

---

## 7. Background Job Workflow & Concurrency Control

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Router as API Router
    participant LockMgr as Job Worker Mutex Manager
    participant Worker as Background Worker Task
    participant DB as PostgreSQL

    Client->>Router: POST /projects/{id}/analyze
    Router->>LockMgr: acquire_project_lock(project_id)
    alt Project Already Running
        LockMgr-->>Router: Lock Failed (Conflict)
        Router-->>Client: 409 Conflict ("Analysis run already in progress")
    else Lock Acquired
        LockMgr-->>Router: Lock Granted
        Router->>DB: Create AnalysisRun (status: pending)
        Router-->>Client: Return AnalysisRun Object
        Router->>Worker: Dispatch Background Task
        Worker->>DB: Update AnalysisRun (status: running)
        Worker->>Worker: Execute Ingestion, Scoring, Recommendations
        alt Execution Success
            Worker->>DB: Update AnalysisRun (status: complete, commit_sha: HEAD)
        else Failure or Cancel
            Worker->>DB: Update AnalysisRun (status: failed/cancelled)
        end
        Worker->>LockMgr: release_project_lock(project_id)
    end
```

---

## 8. Authentication and Authorization Flow (RBAC)

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant AuthAPI as Auth Router (/api/auth)
    participant Sec as Security Engine (PBKDF2/JWT)
    participant Guard as Project Membership Guard
    participant DB as PostgreSQL

    User->>AuthAPI: POST /api/auth/login {email, password}
    AuthAPI->>DB: Lookup User by Email
    AuthAPI->>Sec: Verify PBKDF2-HMAC-SHA256 Hash
    Sec-->>AuthAPI: Valid
    AuthAPI->>Sec: Generate JWT (sub: user_id, exp: 7 days)
    AuthAPI-->>User: {access_token, token_type: Bearer, user}

    User->>Guard: Request /api/projects/{id}/analyze with Bearer Token
    Guard->>Sec: Decode & Validate JWT Signature
    Sec-->>Guard: user_id
    Guard->>DB: Query project_members (project_id, user_id)
    alt Member has Owner or Analyst Role
        Guard-->>User: 200 OK (Proceed to Action)
    else Member has Viewer Role
        Guard-->>User: 403 Forbidden ("Insufficient project permissions")
    else No Membership Assigned
        Guard-->>User: 403 Forbidden ("Project access denied")
    end
```

---

## 9. Database Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    USERS ||--o{ PROJECT_MEMBERS : has
    USERS ||--o{ AUDIT_LOGS : generates
    PROJECTS ||--o{ PROJECT_MEMBERS : assigns
    PROJECTS ||--o{ REPOSITORIES : contains
    PROJECTS ||--o{ DEVELOPERS : employs
    PROJECTS ||--o{ ANALYSIS_RUNS : executes
    PROJECTS ||--o{ AUDIT_LOGS : logs
    REPOSITORIES ||--o{ MODULES : organizes
    REPOSITORIES ||--o{ FILES : contains
    REPOSITORIES ||--o{ COMMITS : tracks
    DEVELOPERS ||--o{ DEVELOPER_ALIASES : unifies
    DEVELOPERS ||--o{ COMMITS : authors
    DEVELOPERS ||--o{ KNOWLEDGE_SCORES : possesses
    MODULES ||--o{ FILES : aggregates
    MODULES ||--o{ MODULE_DEPENDENCIES : requires
    MODULES ||--o{ KNOWLEDGE_SCORES : targets
    MODULES ||--o{ RISK_SCORES : evaluates
    ANALYSIS_RUNS ||--o{ KNOWLEDGE_SCORES : records
    ANALYSIS_RUNS ||--o{ RISK_SCORES : records
    ANALYSIS_RUNS ||--o{ RESILIENCE_SCORES : computes
    ANALYSIS_RUNS ||--o{ RECOMMENDATIONS : produces

    USERS {
        uuid id PK
        string email UK
        string hashed_password
        string role
        boolean is_active
        datetime created_at
    }

    PROJECTS {
        uuid id PK
        string name
        json risk_config
        int rescan_interval_hours
        boolean is_demo
    }

    ANALYSIS_RUNS {
        uuid id PK
        uuid project_id FK
        string status
        string scan_mode
        string rescan_type
        string commit_sha
        json stage_status
        json progress
    }

    MODULES {
        uuid id PK
        uuid repository_id FK
        string name
        string path_prefix
        int loc
    }

    RISK_SCORES {
        uuid id PK
        uuid module_id FK
        uuid analysis_run_id FK
        float score
        string level
        int bus_factor
        float concentration_pct
        boolean is_critical_knowledge_area
    }
```

---

## 10. Developer-Module Knowledge Graph

```mermaid
graph LR
    subgraph Devs ["Developers"]
        D1["Alice (Lead Backend)"]
        D2["Bob (Frontend Specialist)"]
        D3["Charlie (Infra & DevOps)"]
    end

    subgraph Mods ["Modules"]
        M1["backend/auth (Risk: MODERATE, BF: 2)"]
        M2["backend/api (Risk: CRITICAL, BF: 1)"]
        M3["frontend/cosmos (Risk: LOW, BF: 2)"]
        M4["infra/docker (Risk: HIGH, BF: 1)"]
    end

    D1 -->|Knowledge: 85%| M1
    D1 -->|Knowledge: 92%| M2
    D2 -->|Knowledge: 15%| M1
    D2 -->|Knowledge: 88%| M3
    D3 -->|Knowledge: 12%| M3
    D3 -->|Knowledge: 95%| M4

    M2 -->|Imports & Calls| M1
    M3 -->|Consumes REST API| M2
    M2 -->|Runs In| M4
```

---

## 11. Multi-Factor Risk Scoring Workflow

```mermaid
flowchart TD
    ModData[Module Git Activity & Code Structure] --> Factor1[1. Knowledge Concentration (0-1)]
    ModData --> Factor2[2. Bus Factor Inverted Risk (0-1)]
    ModData --> Factor3[3. Documentation Deficit (0-1)]
    ModData --> Factor4[4. Cyclomatic Complexity Score (0-1)]
    ModData --> Factor5[5. Code Churn in Past 90d (0-1)]
    ModData --> Factor6[6. In-Degree & Out-Degree Centrality (0-1)]

    Config[Project Risk Weights Configuration] --> WeightSum[Weighted Linear Combination]
    Factor1 --> WeightSum
    Factor2 --> WeightSum
    Factor3 --> WeightSum
    Factor4 --> WeightSum
    Factor5 --> WeightSum
    Factor6 --> WeightSum

    WeightSum --> RawScore[Raw Module Risk: 0.0 to 100.0]
    RawScore --> LOCShare[Module LOC Share Adjustment]
    LOCShare --> FinalRisk[Final Module Risk Score]

    FinalRisk --> Categorize{Risk Level}
    Categorize -->|Score < 30| Low[LOW]
    Categorize -->|30 <= Score < 55| Moderate[MODERATE]
    Categorize -->|55 <= Score < 75| High[HIGH]
    Categorize -->|Score >= 75| Critical[CRITICAL]
```

---

## 12. Bus Factor Calculation Workflow

```mermaid
flowchart TD
    StartMod[Select Module] --> FilterCommits[Filter Commits within Recency Window]
    FilterCommits --> ApplyDecay[Apply Exponential Half-Life Decay: 0.5 ^ (age / half_life)]
    ApplyDecay --> SumAuthorScores[Compute Effective Author Ownership Shares]
    SumAuthorScores --> SortAuthors[Sort Authors Descending by Normalized Share]
    SortAuthors --> InitLoop[Set Cumulative Share = 0, Count = 0]
    InitLoop --> NextAuthor[Add Next Author Share to Cumulative]
    NextAuthor --> CheckThreshold{Cumulative Share >= Threshold (e.g. 80%)?}
    CheckThreshold -->|No| IncrCount[Increment Count by 1] --> NextAuthor
    CheckThreshold -->|Yes| BusFactorResult[Bus Factor = Count + 1]
    BusFactorResult --> Output[Assign Bus Factor to Module Record]
```

---

## 13. System Resilience Analysis Workflow

```mermaid
flowchart TD
    AllModules[All Project Modules & Graph Edges] --> BFMetric[1. Average Bus Factor Across Modules]
    AllModules --> ConcMetric[2. Low-Concentration Module Ratio]
    AllModules --> DocMetric[3. Project Documentation Coverage]
    AllModules --> ModRisk[4. Inverse Aggregate Module Risk]
    AllModules --> Redundancy[5. Key Component Developer Redundancy]

    BFMetric --> AggregateFormula["Resilience Score = 100 * (w1*BF + w2*Conc + w3*Doc + w4*Risk + w5*Redundancy)"]
    ConcMetric --> AggregateFormula
    DocMetric --> AggregateFormula
    ModRisk --> AggregateFormula
    Redundancy --> AggregateFormula

    AggregateFormula --> BoundedScore[Resilience Score: 0 to 100]
    BoundedScore --> LabelClassify{Resilience Label}
    LabelClassify -->|Score >= 80| Good["GOOD (Resilient Architecture)"]
    LabelClassify -->|60 <= Score < 80| Mod["MODERATE (Acceptable with Hotspots)"]
    LabelClassify -->|40 <= Score < 60| AtRisk["AT_RISK (Vulnerable to Turnover)"]
    LabelClassify -->|Score < 40| Crit["CRITICAL (Severe Knowledge Fragility)"]
```

---

## 14. Developer Unavailability Simulation

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as Engineering Manager / Analyst
    participant SimAPI as Simulation API (/simulations/developer-unavailability)
    participant SimEngine as Simulation Engine
    participant DB as PostgreSQL

    Analyst->>SimAPI: POST {project_id, developer_ids: [dev_id_1, dev_id_2]}
    SimAPI->>DB: Load Project Dependency Graph & Module Ownerships
    SimAPI->>SimEngine: Execute Virtual Departure Simulation
    SimEngine->>SimEngine: Nullify Departing Developers' Knowledge Shares
    SimEngine->>SimEngine: Re-normalize Remaining Developers per Module
    SimEngine->>SimEngine: Recompute Bus Factor for Each Module
    SimEngine->>SimEngine: Calculate Knowledge Loss % & Orphaned Modules
    SimEngine->>SimEngine: Traverse Graph for Cascading Risk Propagation
    SimEngine->>SimEngine: Identify Best Backup Candidates (Cosine / Overlap Match)
    SimEngine->>SimEngine: Recompute Overall System Resilience (Before vs After)
    SimEngine-->>SimAPI: Return Simulation Impact Assessment
    SimAPI-->>Analyst: Display Impact Delta, Orphaned Modules, & Successor Candidates
```

---

## 15. Rule-Based Deterministic Recommendation Engine

```mermaid
flowchart TD
    InputMetrics[Computed Analysis Metrics: Risk, Bus Factor, Churn, Docs, Centrality] --> R1{Bus Factor <= 1 & Level in HIGH/CRITICAL?}
    R1 -->|Yes| Rec1[Emit: Low Bus Factor Recommendation & Pairing Action]
    R1 -->|No| R2{Knowledge Concentration >= 75%?}

    R2 -->|Yes| Rec2[Emit: High Knowledge Concentration & Cross-Training Action]
    R2 -->|No| R3{Documentation Score < 0.40 & Score >= 50?}

    R3 -->|Yes| Rec3[Emit: Missing Documentation Deficit & Runbook Request]
    R3 -->|No| R4{Complexity > 15 & Risk in HIGH/CRITICAL?}

    R4 -->|Yes| Rec4[Emit: High Complexity & Refactoring / Modularization Action]
    R4 -->|No| R5{Change Frequency >= 50 & Bus Factor <= 2?}

    R5 -->|Yes| Rec5[Emit: High Churn Hotspot & Mandatory Code Review Request]
    R5 -->|No| R6{Dependency In-Degree >= 4 & Risk in HIGH/CRITICAL?}

    R6 -->|Yes| Rec6[Emit: Architectural Bottleneck & Decoupling Action]
    R6 -->|No| R7{Month-over-month Single Author Churn Trending Up?}

    R7 -->|Yes| Rec7[Emit: Knowledge Drift Warning & Task Diversification]
    R7 -->|No| DoneRecs[Sort Recommendations by Severity: CRITICAL -> HIGH -> MODERATE -> LOW]
```

---

## 16. Deployment Architecture

```mermaid
flowchart TD
    subgraph HostEnvironment ["Production Host / VM (Docker & Docker Compose)"]
        subgraph Ports ["Published Ports"]
            P80["Port 80 / 443 (HTTP/S)"]
            P8000["Port 8000 (Internal/Backend)"]
            P5432["Port 5432 (Postgres Internal)"]
        end

        subgraph Containers ["Docker Compose Services"]
            FrontendContainer["frontend (Nginx / Vite SPA)"]
            BackendContainer["backend (FastAPI / Gunicorn / Uvicorn Workers)"]
            PostgresContainer["postgres (PostgreSQL 16 Alpine)"]
        end

        subgraph Volumes ["Persistent Storage Volumes"]
            PGData[("postgres_data (Persistent Database Files)")]
            AppCode["Backend & Frontend Sandboxes"]
        end
    end

    P80 --> FrontendContainer
    FrontendContainer -->|Proxy /api| BackendContainer
    BackendContainer --> PostgresContainer
    PostgresContainer --> PGData
```

---

## 17. CI/CD Pipeline Workflow

```mermaid
flowchart LR
    PushEvent([Git Push / PR]) --> CI_Backend[Job 1: Backend CI]
    PushEvent --> CI_Frontend[Job 2: Frontend CI]
    PushEvent --> CI_Docker[Job 3: Compose Validation]

    subgraph BackendCI ["Backend Job (Python 3.11)"]
        PyDeps[Install Dependencies] --> AlembicSQL[Verify Alembic Offline SQL]
        AlembicSQL --> Pytest[Run Pytest Suite]
    end

    subgraph FrontendCI ["Frontend Job (Node.js 20)"]
        NPMInstall[NPM Install] --> ESLint[Run ESLint]
        ESLint --> Vitest[Run Vitest Suite]
        Vitest --> ViteBuild[Build Production Bundle]
    end

    subgraph DockerCI ["Docker Compose Job"]
        ComposeCheck[docker compose config validation]
    end

    CI_Backend --> MergeGate{All Passed?}
    CI_Frontend --> MergeGate
    CI_Docker --> MergeGate
    MergeGate -->|Yes| Deploy([Ready for Production Deploy])
    MergeGate -->|No| Block([Block Merge & Notify])
```

---

## 18. Error Handling and Safe Rollback Workflow

```mermaid
flowchart TD
    StartTask[Start Background Analysis Run] --> ReadStable[Read Current Repository Checkpoint SHA]
    ReadStable --> RunStage[Execute Ingestion & Git Parsing]
    
    RunStage --> CheckStageErr{Stage Error or Crash?}
    CheckStageErr -->|Yes| CatchErr[Catch Exception / Cancellation Signal]
    CheckStageErr -->|No| NextStages[Execute Knowledge, Risk & Graph Engines]

    NextStages --> CheckEngineErr{Engine Error?}
    CheckEngineErr -->|Yes| CatchErr
    CheckEngineErr -->|No| SaveResults[Persist All Metric Records]

    SaveResults --> CommitCheckpoint[Update Repository Checkpoint SHA to New Head]
    CommitCheckpoint --> SetComplete[Mark AnalysisRun: COMPLETE]

    CatchErr --> Rollback[Restore Repository Checkpoint SHA to Previous Stable SHA]
    Rollback --> MarkFailed[Mark AnalysisRun: FAILED / CANCELLED with Error Message]
    MarkFailed --> ReleaseLock[Release Project Concurrency Mutex]
    SetComplete --> ReleaseLock
```

---

## 19. Historical Analysis Snapshot Lifecycle

```mermaid
stateDiagram-v2
    [*] --> InitialRun: First Repository Analysis
    InitialRun --> Snapshot1: Persist AnalysisRun #1 (Metrics, Knowledge, Resilience R1)
    
    Snapshot1 --> GitActivity: Developers Commit Upstream Code
    GitActivity --> IncrementalRescan: Trigger Rescan (Manual or Cron)
    
    IncrementalRescan --> Snapshot2: Persist AnalysisRun #2 (Metrics, Knowledge, Resilience R2)
    
    Snapshot2 --> RunComparison: User Requests Run Comparison
    RunComparison --> ComputeDiffs: Compare R1 vs R2
    
    state ComputeDiffs {
        [*] --> ResilienceDelta: (R2.score - R1.score)
        ResilienceDelta --> ModuleDeltas: Track Module Score Shifts
        ModuleDeltas --> NewRisks: Detect Newly High/Critical Modules
        NewRisks --> ResolvedRisks: Detect Resolved Hotspots
    }
    
    ComputeDiffs --> DiffReport: Display Side-by-Side Diff & Export JSON/CSV
```

---

## 20. Scheduled Rescan Workflow

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as Background Cron Scheduler
    participant DB as PostgreSQL
    participant Worker as Background Worker Pool
    participant Git as Git Origin Remote

    Scheduler->>DB: Query Projects with rescan_interval_hours > 0
    DB-->>Scheduler: List of Active Scheduled Projects
    loop For Each Scheduled Project
        Scheduler->>DB: Check Latest AnalysisRun completed_at
        alt Elapsed Time >= rescan_interval_hours
            Scheduler->>Worker: Check if Project Concurrency Lock Available
            alt Lock Free
                Scheduler->>Worker: Dispatch Background Rescan (type: scheduled)
                Worker->>Git: git fetch origin
                Worker->>Worker: Ingest Delta & Recompute Metrics
                Worker->>DB: Persist New Analysis Snapshot & Update Checkpoint
            else Lock Busy
                Scheduler->>Scheduler: Skip and retry on next tick
            end
        else Interval Not Yet Elapsed
            Scheduler->>Scheduler: Sleep until next evaluation cycle
        end
    end
```
