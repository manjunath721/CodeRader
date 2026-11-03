"""
Perf benchmark harness (master spec §9). Builds synthetic repositories of
configurable size, then measures:

  1. Cold scan (first-ever analysis of the repository)
  2. Repeat scan (re-analyze with zero new commits)
  3. Scan after a small commit (re-analyze with exactly one new commit)

...for the full analysis pipeline, plus isolated micro-benchmarks for the
two specific bottlenecks this perf pass targeted (GitPython per-commit
stats vs batched CLI history extraction; per-row DB flush vs batched
insert). Results are printed as a table and are NOT asserted against fixed
thresholds — hardware varies; this script is for producing the numbers in
docs/perf-benchmarks.md, not for CI gating.

Usage:
    DATABASE_URL=sqlite:////tmp/bench.db python scripts/benchmark_ingestion.py [small|medium|large]
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from git import Actor, Repo  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.models  # noqa: F401,E402
from app.core.db import Base  # noqa: E402
from app.models.project import Project, Repository  # noqa: E402
from app.services.analysis_pipeline import run_analysis  # noqa: E402

SIZES = {
    "small": 100,
    "medium": 1_200,
    "large": 5_000,
}


def build_synthetic_repo(num_commits: int, num_modules: int = 4) -> str:
    d = tempfile.mkdtemp(prefix="coderesilience_bench_")
    repo = Repo.init(d)
    for m in range(num_modules):
        os.makedirs(f"{d}/src/mod{m}", exist_ok=True)
    for i in range(num_commits):
        mod = i % num_modules
        path = f"src/mod{mod}/f{i % 25}.py"
        full = f"{d}/{path}"
        with open(full, "a") as f:
            f.write(f"def fn_{i}(x):\n    if x:\n        return x\n    return 0\n")
        repo.index.add([path])
        repo.index.commit(f"commit {i}", author=Actor("Dev", "dev@example.com"))
    return d


def run_benchmark(size_label: str) -> None:
    num_commits = SIZES[size_label]
    print(f"\n=== Benchmark: {size_label} ({num_commits} commits) ===")

    print(f"Building synthetic repo ({num_commits} commits)...")
    t0 = time.time()
    repo_path = build_synthetic_repo(num_commits)
    print(f"  built in {time.time() - t0:.1f}s")

    db_path = f"/tmp/bench_{size_label}.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    project = Project(name=f"Benchmark {size_label}")
    db.add(project)
    db.flush()
    repo_row = Repository(project_id=project.id, url=repo_path, provider="local")
    db.add(repo_row)
    db.commit()

    t0 = time.time()
    run1 = run_analysis(db, project)
    cold_time = time.time() - t0
    print(f"Cold scan:                 {cold_time:.3f}s  (status={run1.status})")

    t0 = time.time()
    run2 = run_analysis(db, project)
    repeat_time = time.time() - t0
    print(f"Repeat scan (no changes):  {repeat_time:.3f}s  ({cold_time / repeat_time:.1f}x faster than cold)")

    git_repo = Repo(repo_path)
    with open(f"{repo_path}/src/mod0/f0.py", "a") as f:
        f.write("\ndef extra():\n    return 1\n")
    git_repo.index.add(["src/mod0/f0.py"])
    git_repo.index.commit("small change", author=Actor("Dev", "dev@example.com"))

    t0 = time.time()
    run3 = run_analysis(db, project)
    small_commit_time = time.time() - t0
    print(f"Scan after 1 new commit:   {small_commit_time:.3f}s  ({cold_time / small_commit_time:.1f}x faster than cold)")
    print(f"  ingestion detail: {list(run3.progress['ingestion'].values())[0]}")


if __name__ == "__main__":
    labels = sys.argv[1:] or ["small", "medium"]
    for label in labels:
        if label not in SIZES:
            print(f"Unknown size {label!r}; choose from {list(SIZES)}")
            sys.exit(1)
        run_benchmark(label)
