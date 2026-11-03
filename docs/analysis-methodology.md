# Analysis Methodology

This document specifies exactly how raw repository data becomes the metrics
shown in the dashboard. It exists so every number in the product is
academically defensible and explainable (master spec §40).

## 1. Developer identity normalization

Raw Git authorship is `(name, email)` per commit. Two identities are
proposed as "the same developer" only when a configurable rule matches:

- exact email match, OR
- exact normalized-name match (case-insensitive, punctuation-stripped) AND
  a shared email domain, OR
- an explicit manual alias created by the user (`developer_aliases` table)

No automatic fuzzy/ML merge is applied silently — proposed merges below the
"exact" rules are surfaced to the user as **suggestions** to confirm, never
auto-applied. This directly follows §6's "do not blindly merge identities."

## 2. Module detection

Modules are inferred from top-level (configurable depth, default 2) source
directories, filtered to exclude build/vendor/test-fixture paths (`node_modules`,
`dist`, `build`, `.venv`, `vendor`, `__pycache__`, etc). A module is a
first-class row (`modules` table) with a `path_prefix`; every file maps to
at most one module by longest-prefix match. This is a heuristic, documented
as such — projects with unconventional layouts may need manual module
remapping (Phase-2 UI enhancement).

## 3. Knowledge score (per developer × module)

```
knowledge_score(d, m) = 100 × normalize(
    w1 * contribution_score(d, m) +
    w2 * recency_score(d, m) +
    w3 * module_experience(d, m) +
    w4 * review_score(d, m) +
    w5 * issue_score(d, m)
)
```

Default weights (configurable in `app/risk/config.py`):
`w1=0.35, w2=0.15, w3=0.20, w4=0.20, w5=0.10` (sum to 1.0).

Component definitions:

- **contribution_score(d, m)** — normalized share of (commits touching m by
  d, weighted by lines-changed-log-dampened) among all contributors to m.
  Log-dampening (`log1p(lines_changed)`) prevents one huge commit from
  dominating the score.
- **recency_score(d, m)** — exponential decay of d's most recent commit to
  m: `exp(-λ * days_since_last_commit)`, default half-life 90 days.
- **module_experience(d, m)** — normalized count of distinct commits by d to
  m over the full history (breadth of repeated engagement, not just volume).
- **review_score(d, m)** — normalized count of PR reviews by d on PRs that
  touched m (0 if no PR data available, e.g. non-GitHub repos).
- **issue_score(d, m)** — normalized count of issues by d linked/labeled to m
  (0 if no issue data available).

All five components are min-max normalized to `[0, 1]` across developers
*within that module* before weighting, so the final score reflects relative
standing on that module, not absolute commit volume across the project.

**Explicitly not claimed:** this score is called *"repository-derived
knowledge familiarity"* throughout the UI — it is not asserted to measure a
developer's real-world skill or code quality (§8).

## 4. Knowledge concentration (HHI)

For module `m` with knowledge scores `s_1..s_n` (renormalized to sum to 100
across contributors of `m`), concentration uses the Herfindahl–Hirschman
Index, standard in economics for measuring market concentration:

```
HHI(m) = Σ (share_i)²          where share_i = s_i / Σs, expressed as a percent (0–100 scale share, so HHI ranges 0–10000)
concentration_pct(m) = HHI(m) / 100   → normalized display value, 0–100
```

A single-owner module (`share = 100%`) has `HHI = 10000` → `concentration_pct = 100`.
An evenly-split 5-way module has `HHI = 2000` → `concentration_pct = 20`.
HHI is chosen over "top contributor %" alone because it penalizes *any*
skew, not just a single dominant owner — documented rationale for graders.

## 5. Bus factor

```
meaningful_contributor(d, m)  :=  knowledge_score(d, m) >= threshold   (default threshold = 10, configurable)
bus_factor(m) = count(d such that meaningful_contributor(d, m))
```

`project_bus_factor` = minimum bus factor across modules classified as
"critical" (see risk-model.md §Criticality). This is explicitly labeled an
**approximation** in the UI — a low-effort heuristic proxy for the informal
"truck factor" concept, not a formally validated metric.

## 6. Knowledge drift

Knowledge scores are recomputed at each monthly checkpoint using only
commits up to that checkpoint's date (a rolling historical replay, not a
separate live computation), producing a time series per developer/module.
Drift is flagged when a developer's module share increases by more than a
configurable threshold (default 10 percentage points) over 3 consecutive
checkpoints — "Knowledge concentration is increasing" (§14).

## 7. Hidden expert detection

A developer `d` is flagged as a **potential secondary expert** for module `m`
if `d` is not the primary knowledge holder but:

```
secondary_expert_score(d, m) = normalize(
    0.35 * review_score(d, m) +
    0.25 * issue_score(d, m) +
    0.20 * related_module_score(d, m) +      # knowledge in modules that depend_on/are depended_on_by m
    0.20 * technology_overlap_score(d, m)    # shared technology tags with m's primary tech stack
)
```

`related_module_score` and `technology_overlap_score` let a developer whose
direct commit history on `m` is thin still surface as a credible backup,
addressing §15's example (Developer B: heavy reviewer/related-module
contributor despite only 10% of commits).

## 8. Backup candidate ranking

Backup candidates for module `m` are ranked by a **compatibility score**,
distinct from `knowledge_score` in that it explicitly includes related-module
and technology signals so non-obvious candidates surface:

```
compatibility(d, m) = normalize(
    0.40 * knowledge_score(d, m) +
    0.25 * related_module_score(d, m) +
    0.15 * technology_overlap_score(d, m) +
    0.10 * review_score(d, m) +
    0.10 * recency_score(d, m)
)
```

Displayed and labeled as a **"repository-derived backup candidate"** —
never framed as a personnel/HR recommendation (§21).

## 9. Limitations (documented, not hidden)

- No signal for informal knowledge (Slack, pairing, tribal knowledge outside Git/GitHub).
- Review/issue signals are 0 for repositories without GitHub PR/issue data — bus factor and risk scores degrade gracefully to commit-based signals only, and the UI labels which signals were available for that analysis run.
- Module detection is directory-heuristic; monorepos with non-standard layout need manual remapping.
- Complexity metrics are static-analysis proxies, not runtime/behavioral complexity.
- All simulation outputs are repository-derived *potential* impact estimates, not predictions of actual production incidents or employee-replacement probability (§18, §20).
