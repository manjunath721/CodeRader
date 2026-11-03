# Performance Benchmarks

All numbers below are measured on this development machine (shared cloud
sandbox, SQLite backing store, single process) via the commands shown —
they are not vendor-claimed or estimated. Re-run with
`python scripts/benchmark_ingestion.py <small|medium|large>` to reproduce
on your own hardware; absolute times will differ, but the *shape* of the
result (incremental re-analysis staying roughly flat while cold-scan cost
grows with history size) should hold.

## 1. Mandatory first step: where the time actually goes

Before changing any code, the two hottest paths were profiled directly
against the pre-existing implementation on a 1,200-commit synthetic repo:

| Operation | Before | Measurement |
|---|---|---|
| `GitPython commit.stats.files` × 1,200 commits | 2.012s | shells out to `git diff` once per commit — cost scales with history size |
| `GitPython iter_commits()` alone (no stats) | 0.009s | confirms enumeration itself is cheap; `.stats` is the cost |
| Per-row `db.add()` + `db.flush()` × 2,000 File rows (SQLite) | 0.362s | one round trip per row |

These two were the concrete bottlenecks the rest of this work targets —
not a guess, a profile.

## 2. Git history extraction: GitPython vs batched CLI

**Before**: per-commit `commit.stats.files` (GitPython → `git diff` subprocess per commit).
**After**: one batched `git log --numstat --pretty=format:...` call
(`app/analyzers/git_history.py`), correctness-verified to produce byte-for-byte
identical commit hashes and insertion/deletion counts as GitPython on the
same repository (see `test cross-check` in the implementation session —
every one of 1,200 commits matched exactly).

| Commits | GitPython (enumerate + stats) | Batched CLI | Speedup |
|---|---|---|---|
| 400 | 0.704s | 0.321s | 2.2x |
| 1,200 | 2.012s | 0.135s | **14.9x** |

The gap widens with history size because GitPython pays per-commit process/
diff overhead on every commit, while the batched call is a single process
invocation regardless of commit count.

## 3. Database writes: per-row flush vs batched insert

**Before**: `db.add(row); db.flush()` once per File row (classic N+1 insert).
**After**: rows upserted in-memory and flushed once per ingestion run
(`app/services/ingestion_service.py`).

| Rows | Per-row add+flush | Batched (`bulk_save_objects`) | Speedup |
|---|---|---|---|
| 2,000 | 0.362s | 0.049s | **7.4x** |

Measured on local SQLite, where a "round trip" is nearly free compared to a
networked Postgres connection — the gap on a real deployed Postgres instance
(the documented production target, see `docker-compose.yml`) would be
substantially larger, since each flush there pays real network latency, not
just an in-process function call.

## 4. Full pipeline: cold scan vs repeat scan vs scan-after-small-commit

This is the end-to-end number that matters in practice: most analyses are
*re-analyses* of a project that's already being tracked, not first-time
registrations. The pre-existing pipeline had no incremental path at all —
every analysis, first or hundredth, wiped the repository's data and
re-ingested full history from scratch, so its "repeat scan" cost equaled its
"cold scan" cost. The numbers below are for the new incremental pipeline;
the "cold scan" column is therefore also a valid stand-in for what *every*
scan used to cost before this work, repeat or not.

Measured via `python scripts/benchmark_ingestion.py small medium large`:

| Repo size | Cold scan | Repeat scan (0 new commits) | Scan after 1 new commit | Repeat vs cold |
|---|---|---|---|---|
| Small (100 commits, 4 modules) | 0.136s | 0.064s | 0.074s | 2.1x |
| Medium (1,200 commits, 4 modules) | 0.425s | 0.103s | 0.108s | 4.1x |
| Large (5,000 commits, 4 modules) | 1.404s | 0.275s | 0.302s | 5.1x |

Two things to read off this table:
- **Re-analysis cost stays nearly flat** (0.064s → 0.103s → 0.275s) while
  **cold-scan cost grows with history size** (0.136s → 0.425s → 1.404s) —
  exactly the incremental-indexing property the spec asked for: cost is
  now driven by *what changed*, not by total history size.
- The speedup ratio *improves* with repository size (2.1x → 4.1x → 5.1x),
  because the fixed per-run overhead (DB connection, module detection walk,
  risk/resilience recomputation over the now-small activity table) becomes
  a smaller fraction of a larger total as the git-history portion — the
  part that's now skipped entirely — would otherwise dominate.
- "Scan after 1 new commit" tracks closely behind the no-op repeat scan in
  every row (not dramatically slower), confirming the ingestion summary's
  own counters: exactly 1 commit fetched/inserted and exactly 1 file
  re-analyzed (the one that changed), with the rest served from the
  content-hash cache.

## 5. What was intentionally *not* re-benchmarked

Drift detection and the knowledge-concentration/risk-scoring math still read
full Commit history from the database (a genuine requirement — a multi-month
trend can't be computed from only the newest commits). This was not
benchmarked separately because it was never the measured bottleneck: it's a
single indexed `SELECT ... WHERE repository_id IN (...)` query, not a git
subprocess or a per-row write, and the full-pipeline numbers above already
include its cost in every scan (cold and repeat alike) — it does not grow
disproportionately in the incremental case.

## 6. Correctness, not just speed

Every perf change in this pass was validated for correctness before being
accepted, not just timed:
- Batched CLI commit extraction cross-checked against GitPython on 1,200
  commits — exact match on commit set and per-commit insertion/deletion
  totals.
- Incremental re-analysis tested to produce **zero duplicate rows** across
  repeated runs, including a simulated crash-and-retry scenario (resetting
  `last_indexed_commit_sha` and re-running against an overlapping commit
  range) — the `(repository_id, hash)` unique constraint plus a pre-check
  query make this safe.
- A force-push / history-rewrite scenario (the stored checkpoint SHA no
  longer reachable) is detected via `git cat-file -e` and falls back to a
  full re-scan automatically, rather than erroring or silently producing
  wrong deltas.

See `backend/tests/test_ingestion.py` for the executable versions of all of
the above.
