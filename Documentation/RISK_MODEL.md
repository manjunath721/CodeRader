# Risk & Resilience Model

## 1. Module risk score

```
risk(m) = 100 × Σ w_i * factor_i(m),   factor_i(m) ∈ [0,1], Σw_i = 1
```

| Factor | Definition | Default weight |
|---|---|---|
| `knowledge_concentration` | `concentration_pct(m) / 100` (see methodology §4) | 0.25 |
| `bus_factor_risk` | `1 / (1 + bus_factor(m))` — inverted, diminishing | 0.20 |
| `documentation_risk` | `1 - documentation_coverage(m)` | 0.15 |
| `complexity_risk` | normalized avg. cyclomatic complexity across m's files | 0.15 |
| `change_frequency_risk` | normalized commit frequency to m over trailing 90 days | 0.15 |
| `dependency_risk` | normalized in-degree + out-degree centrality of m in the module-dependency graph | 0.10 |

All weights are configurable per project (`risk_config` on the project row);
defaults above sum to 1.0. Every module risk response from the API includes
a `factors` breakdown object so the frontend can show *why* — never a
bare number (§12, §42).

### Risk levels

| Range | Label |
|---|---|
| 0–24 | LOW |
| 25–49 | MODERATE |
| 50–74 | HIGH |
| 75–100 | CRITICAL |

## 2. Criticality (distinct from risk — §11)

Criticality flags modules combining **structural importance** with risk,
so a small risky utility module doesn't outrank a risky core module:

```
criticality(m) = risk(m) × structural_importance(m)
structural_importance(m) = normalize(
    0.5 * dependency_centrality(m) +   # how many other modules depend on m
    0.3 * change_frequency(m) +
    0.2 * loc_share(m)                 # module's share of total project LOC
)
```

`criticality(m) >= 70` (configurable) → labeled **CRITICAL KNOWLEDGE AREA**.

## 3. Project resilience score

```
resilience = 100 × (
    0.25 * developer_redundancy +      # avg bus_factor across modules, normalized
    0.20 * knowledge_distribution +    # 1 - avg concentration_pct/100 across modules
    0.20 * documentation_coverage +    # project-wide avg
    0.20 * (1 - avg critical_module_risk/100) +
    0.15 * (1 - dependency_concentration)  # 1 - HHI of module dependency graph
)
```

| Range | Label |
|---|---|
| 80–100 | GOOD |
| 60–79 | MODERATE |
| 35–59 | AT RISK |
| 0–34 | CRITICAL |

## 4. Risk propagation (§20)

Given the module-dependency graph `G` (directed edge `A → B` means B depends
on A), and a module `m` whose knowledge is lost:

```
direct_impact(m) = 1.0
propagated_impact(m') = direct_impact(m) × decay^(shortest_path_length(m, m'))   for each m' reachable from m in G
```

Default `decay = 0.6` per hop (configurable). Propagated impact is converted
to a risk-level label (same thresholds as above) and rendered on the
dependency graph with a clear visual distinction between **direct impact**
(m itself) and **dependency-based potential impact** (downstream modules) —
never claimed as a production-failure prediction (§20).

## 5. Simulation engine (§18–19)

`POST /api/simulations/developer-unavailability`:

1. Remove developer `d`'s knowledge-score contribution from every module.
2. Recompute concentration, bus factor, and risk for every affected module
   using the same formulas as above, on the reduced dataset.
3. Recompute project resilience.
4. `knowledge_potentially_affected_pct` = d's share of total project-wide
   knowledge score, pre-removal.
5. Run risk propagation (§4) from every module where `d` was the primary
   holder.
6. Rank backup candidates for each affected module (methodology §8).
7. Persist a `simulations` + `simulation_results` row so scenarios can be
   compared (§19) and replayed without recomputation.

Multi-failure simulation is the same procedure with a *set* of developers
removed simultaneously, and reuses the identical scoring/risk functions —
no separate code path, which keeps the two consistent by construction.

## 6. Deterministic Rule-Based Recommendations

CodeRadar strictly uses deterministic algorithms and explainable rule trees:

- **Rule Evaluation**: Evaluates computed module metrics (bus factor, concentration %, documentation score, cyclomatic complexity, churn, and architectural centrality) against explicit thresholds.
- **Explainability**: Every recommendation outputs:
  - `title` and `description`
  - `severity` (`CRITICAL`, `HIGH`, `MODERATE`, `LOW`)
  - `rule_type` (e.g. `LOW_BUS_FACTOR`, `HIGH_CONCENTRATION`, `MISSING_DOCUMENTATION`)
  - `triggering_metric` (e.g. `bus_factor=1`, `concentration_pct=85.0%`)
  - `suggested_action` (concrete mitigation steps such as pairing, cross-training, refactoring, or authoring runbooks)
- **Knowledge Transfer Curriculum**: Provides structured 6-point knowledge transfer plans for high-risk single-owner modules.
- **Zero AI / ML**: The entire platform operates without external LLMs or black-box machine learning models.
