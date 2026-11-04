# CodeRadar — Deterministic Analysis, Metrics, & Rule Engine

CodeRadar is an explainable repository intelligence and software engineering risk analysis platform.
It relies exclusively on deterministic algorithms, polyglot static parsing, graph theory, and rule-based decision trees.
It does **not** use AI, LLMs, or non-deterministic machine learning.

---

## 1. Core Principles

1. **Deterministic & Reproducible**: Re-running an analysis over the identical Git commit tree produces identical risk scores, bus factor metrics, and recommendations.
2. **Explainable Recommendations**: Every emitted recommendation cites its exact triggering metric, threshold rule, affected module or engineer, and concrete suggested actions.
3. **Repository Intelligence, Not Employee Surveillance**: Git metrics serve strictly as engineering proxies for module familiarity and architectural risk—never as measures of employee productivity or performance.

---

## 2. Developer Knowledge Scoring

Developer knowledge concentration measures how familiarity with a codebase is distributed across contributors.

### Exponential Recency Decay

Recent contributions reflect current mental models better than historical commits. Contributions decay according to an exponential half-life:

$$w_{\text{recency}} = 0.5^{\frac{\Delta t}{T_{\text{half-life}}}}$$

Where:
- $\Delta t$ is the age of the commit in days.
- $T_{\text{half-life}}$ is configurable via `risk_config.recency_half_life_days` (default: 90 days).

### Composite Knowledge Weighting

A contributor's raw score on a module is computed as:

$$\text{RawScore}(d, m) = w_{\text{lines}} \cdot \text{LOC}_{\text{authored}} + w_{\text{commits}} \cdot \text{Commits}_{\text{authored}} + w_{\text{recent}} \cdot \sum_{\text{commits}} w_{\text{recency}}$$

Normalized across all contributors to module $m$:

$$\text{KnowledgeShare}(d, m) = \frac{\text{RawScore}(d, m)}{\sum_{i} \text{RawScore}(d_i, m)}$$

---

## 3. Bus Factor Calculation

The Bus Factor represents the minimum number of engineers whose sudden unavailability would leave a module without sufficient operational and architectural knowledge.

### Algorithm
1. Compute the normalized `KnowledgeShare` for each developer on module $m$.
2. Sort developers descending by knowledge share: $d_1, d_2, \dots, d_n$.
3. Accumulate shares until reaching the coverage threshold (default: 80% or 0.80):
   $$\sum_{i=1}^{k} \text{KnowledgeShare}(d_i, m) \ge 0.80$$
4. The Bus Factor is the count $k$:
   $$\text{BusFactor}(m) = k$$

A Bus Factor of 1 indicates extreme fragility (single point of failure).

---

## 4. Multi-Factor Module Risk Scoring

Module risk is a composite metric bounded between 0.0 and 100.0, derived from six structural and organizational risk factors:

1. **Knowledge Concentration Risk ($F_{\text{concentration}}$)**:
   $$F_{\text{concentration}} = \max_{d} \text{KnowledgeShare}(d, m)$$
2. **Bus Factor Inverted Risk ($F_{\text{bf}}$)**:
   $$F_{\text{bf}} = \max\left(0, 1 - \frac{\text{BusFactor}(m)}{\text{Threshold}_{\text{bf}}}\right)$$
3. **Documentation Deficit ($F_{\text{doc}}$)**:
   $$F_{\text{doc}} = 1.0 - \text{DocumentationScore}(m)$$
   Where documentation score measures presence of READMEs, docstrings, and specification docs.
4. **Complexity Risk ($F_{\text{complexity}}$)**:
   $$F_{\text{complexity}} = \min\left(1.0, \frac{\text{AvgCyclomaticComplexity}(m)}{25.0}\right)$$
5. **Churn Risk ($F_{\text{churn}}$)**:
   $$F_{\text{churn}} = \min\left(1.0, \frac{\text{CommitsLast90Days}(m)}{100}\right)$$
6. **Dependency Centrality ($F_{\text{centrality}}$)**:
   $$F_{\text{centrality}} = \min\left(1.0, \frac{\text{DegreeCentrality}(m)}{10}\right)$$

### Aggregation Formula

$$\text{RawRisk}(m) = 100 \times \sum_{j=1}^{6} w_j \cdot F_j(m)$$

Where $\sum w_j = 1.0$, configurable in `risk_config.risk_weights`.

### Criticality & Module Scale Adjustment

Modules representing significant portions of total codebase LOC receive scaled criticality weighting:

$$\text{LOCShare}(m) = \frac{\text{LOC}(m)}{\sum_{i} \text{LOC}(m_i)}$$
$$\text{CriticalityScore}(m) = 0.7 \cdot \text{RawRisk}(m) + 30.0 \cdot \min(1.0, 3 \cdot \text{LOCShare}(m))$$

### Risk Levels
- **LOW**: Score < 30.0
- **MODERATE**: 30.0 $\le$ Score < 55.0
- **HIGH**: 55.0 $\le$ Score < 75.0
- **CRITICAL**: Score $\ge$ 75.0

---

## 5. System Resilience Scoring

Resilience measures overall repository health and organizational durability against turnover (0 to 100):

$$\text{Resilience} = 100 \cdot \left(0.35 \cdot \overline{\text{BF}}_{\text{norm}} + 0.25 \cdot (1 - \overline{\text{Conc}}) + 0.20 \cdot \overline{\text{Doc}} + 0.20 \cdot (1 - \overline{\text{Risk}}_{\text{norm}})\right)$$

- **GOOD**: Resilience $\ge$ 80
- **MODERATE**: 60 $\le$ Resilience < 80
- **AT_RISK**: 40 $\le$ Resilience < 60
- **CRITICAL**: Resilience < 40

---

## 6. Deterministic Recommendation Rules

The recommendation engine evaluates rules deterministically over computed metrics:

| Rule ID | Condition | Severity | Suggested Action |
|---|---|---|---|
| `LOW_BUS_FACTOR` | `bus_factor <= 1` & risk in `HIGH`/`CRITICAL` | `CRITICAL` | Identify and train backup maintainers through pairing and code reviews. |
| `HIGH_CONCENTRATION` | `concentration_pct >= 75%` | `HIGH` | Conduct knowledge-transfer sessions and distribute ongoing tasks. |
| `MISSING_DOCUMENTATION` | `documentation_score < 0.40` & `score >= 50` | `HIGH` | Author architecture overviews, onboarding guides, and runbooks. |
| `HIGH_COMPLEXITY` | `complexity_avg > 15` & risk in `HIGH`/`CRITICAL` | `HIGH` | Refactor large routines, split monolithic files, and decouple dependencies. |
| `HIGH_CHURN` | `change_frequency_90d >= 50` & `bus_factor <= 2` | `MODERATE` | Increase test coverage, automate regression tests, and require two reviewers. |
| `HIGH_CENTRALITY` | `in_degree >= 4` & risk in `HIGH`/`CRITICAL` | `HIGH` | Review architectural coupling and decouple downstream modules. |
| `DRIFT_INCREASING` | Month-over-month concentration trend upward | `MODERATE` | Allocate incoming features to alternative engineers. |
| `CRITICAL_KNOWLEDGE_AREA` | Module criticality exceeds project threshold | `CRITICAL` | Require formal succession plans and cross-team review approval. |

---

## 7. Structured Knowledge Transfer Plan Curriculum

For any high-risk module, CodeRadar provides a standardized 6-point knowledge transfer plan:
1. **Architectural boundaries & component interfaces**
2. **Core data models, persistence, and state management**
3. **Operational runbooks and deployment procedures**
4. **Common failure modes, error handling, and recovery steps**
5. **Critical APIs, dependency contracts, and integration points**
6. **Testing strategy, regression suites, and debugging workflows**
