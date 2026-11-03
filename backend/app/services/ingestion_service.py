"""
Repository ingestion service (master spec §6, §7; architecture.md §3
stages 1-9) — perf-hardened version.

Key differences from the original wipe-and-recreate design, all measured or
reasoned about in docs/perf-benchmarks.md:

- Commit history is fetched via a single batched `git log --numstat` CLI
  call (app.analyzers.git_history) instead of per-commit GitPython
  `.stats.files` — measured 14.9x faster at 1,200 commits.
- When a repository has already been indexed, only commits newer than
  `repository.last_indexed_commit_sha` are fetched and inserted at all
  (`<sha>..HEAD`) — we never re-walk history we've already processed.
  Force-push/rebase (the old SHA no longer reachable) is detected and falls
  back to a full re-scan automatically.
- Files and modules are upserted by (repository_id, path) / (repository_id,
  path_prefix) instead of deleted and recreated every run, which (a) keeps
  their primary keys stable across re-analysis — required for
  KnowledgeScore/RiskScore history to stay meaningful — and (b) lets
  unchanged files skip re-analysis entirely via a content-hash check.
- New Commit rows are bulk-inserted in one batch instead of one
  add()+flush() per row — measured 7.4x faster at 2,000 rows on SQLite
  (networked Postgres will see a larger gap, since each flush there is a
  round trip).
- Developer identity resolution is re-run over the union of existing
  DeveloperAlias rows + any new commits' raw identities (cheap: bounded by
  contributor count, not commit count), then reconciled against existing
  Developer rows so repeat runs don't create duplicates.
"""
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.analyzers.git_clone import QUICK_SCAN_MAX_COMMITS, clone_repository, cleanup_clone
from app.analyzers.git_history import commit_exists, extract_commit_history, get_current_branch, get_head_commit_sha
from app.analyzers.module_dependency_resolver import resolve_module_dependencies
from app.analyzers.module_detector import assign_file_to_module, infer_module_prefixes, module_display_name
from app.analyzers.source.registry import ANALYZER_VERSION, analyze_file, SUPPORTED_EXTENSIONS
from app.core.errors import NoCommitsFoundError
from app.models.activity import Commit, DeveloperModuleActivity
from app.models.code import File as FileModel
from app.models.code import Module, ModuleDependency
from app.models.developer import Developer, DeveloperAlias
from app.models.project import Repository as RepositoryModel
from app.services.identity import RawIdentity, resolve_developers

EXCLUDED_DIRS = {"node_modules", "dist", "build", ".venv", "venv", "vendor", "__pycache__", ".git", "target"}


def _iter_source_files(root: str) -> list[str]:
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            paths.append(rel)
    return paths


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reconcile_developers(
    db: Session, project_id, raw_identities: list[RawIdentity]
) -> dict[tuple[str, str | None], Developer]:
    """
    Re-resolves developer identity groupings over existing aliases + any new
    raw identities (bounded by contributor count, not commit count — cheap
    even for a huge repository), then reuses existing Developer rows where
    an alias already matches rather than creating duplicates.
    """
    existing_aliases = (
        db.query(DeveloperAlias)
        .join(Developer, DeveloperAlias.developer_id == Developer.id)
        .filter(Developer.project_id == project_id)
        .all()
    )
    existing_by_identity: dict[tuple[str, str | None], Developer] = {}
    existing_dev_by_id = {}
    for alias in existing_aliases:
        existing_by_identity[(alias.raw_name, alias.raw_email)] = alias.developer_id
        existing_dev_by_id[alias.developer_id] = alias.developer

    combined_identities = list(raw_identities)
    seen = {(a.raw_name, a.raw_email) for a in existing_aliases}
    for alias in existing_aliases:
        if (alias.raw_name, alias.raw_email) not in seen:
            combined_identities.append(RawIdentity(name=alias.raw_name, email=alias.raw_email))

    resolved_devs = resolve_developers(combined_identities)

    dev_lookup: dict[tuple[str, str | None], Developer] = {}
    for rd in resolved_devs:
        # Does this resolved group already correspond to an existing Developer?
        matched_dev_id = None
        for ident in rd.raw_identities:
            key = (ident.name, ident.email)
            if key in existing_by_identity:
                matched_dev_id = existing_by_identity[key]
                break

        if matched_dev_id:
            dev = existing_dev_by_id[matched_dev_id]
        else:
            dev = Developer(
                project_id=project_id, display_name=rd.display_name,
                primary_email=rd.primary_email, normalized_key=rd.normalized_key,
            )
            db.add(dev)
            db.flush()

        for ident in rd.raw_identities:
            key = (ident.name, ident.email)
            if key not in seen:
                db.add(
                    DeveloperAlias(
                        developer_id=dev.id, raw_name=ident.name, raw_email=ident.email,
                        source="git", confidence="exact", confirmed=True,
                    )
                )
                seen.add(key)
            dev_lookup[key] = dev
        for ident in rd.suggested_merges:
            key = (ident.name, ident.email)
            if key not in seen:
                # Recorded as an unconfirmed alias suggestion — never silently merged (§6).
                db.add(
                    DeveloperAlias(
                        developer_id=dev.id, raw_name=ident.name, raw_email=ident.email,
                        source="git", confidence="suggested", confirmed=False,
                    )
                )
                seen.add(key)

    db.flush()
    return dev_lookup


def ingest_repository(
    db: Session,
    repo_row: RepositoryModel,
    url_or_local_path: str,
    is_local: bool = False,
    scan_mode: str = "full",
    force_full_rescan: bool = False,
) -> dict:
    """
    Runs pipeline stages 1-9 for a single repository row, incrementally
    where possible, and commits all derived rows to the database. Returns a
    summary dict (including real, non-fabricated progress counters) used to
    populate `analysis_runs.progress`.
    """
    clone_path = clone_repository(url_or_local_path, local_path=url_or_local_path if is_local else None, scan_mode=scan_mode)
    try:
        head_sha = get_head_commit_sha(clone_path)
        if head_sha is None:
            raise NoCommitsFoundError()
        current_branch = get_current_branch(clone_path)

        can_resume = (
            not force_full_rescan
            and repo_row.last_indexed_commit_sha is not None
            and repo_row.last_indexed_branch == current_branch
            and commit_exists(clone_path, repo_row.last_indexed_commit_sha)
        )
        since_sha = repo_row.last_indexed_commit_sha if can_resume else None
        max_commits = QUICK_SCAN_MAX_COMMITS if (scan_mode == "quick" and not can_resume) else None

        commit_records = extract_commit_history(clone_path, since_commit_sha=since_sha, max_commits=max_commits)
        if not commit_records and not can_resume:
            raise NoCommitsFoundError()

        # --- Developer identity resolution (existing + any new raw identities) ---
        new_raw_identities = [
            RawIdentity(name=c.author_name or "unknown", email=c.author_email or None) for c in commit_records
        ]
        dev_lookup = _reconcile_developers(db, repo_row.project_id, new_raw_identities)

        # --- Module detection from the current working-tree snapshot (always
        #     re-walked — module layout reflects current state regardless of
        #     which commit range we're processing) ---
        all_paths = _iter_source_files(clone_path)
        source_paths = [p for p in all_paths if any(p.endswith(ext) for ext in SUPPORTED_EXTENSIONS)]
        module_prefixes = infer_module_prefixes(source_paths, depth=2)

        existing_modules = {m.path_prefix: m for m in db.query(Module).filter(Module.repository_id == repo_row.id)}
        module_rows: dict[str, Module] = {}
        for prefix in module_prefixes:
            if prefix in existing_modules:
                module_rows[prefix] = existing_modules[prefix]
            else:
                m = Module(repository_id=repo_row.id, name=module_display_name(prefix), path_prefix=prefix)
                db.add(m)
                db.flush()
                module_rows[prefix] = m

        # --- Source analysis with content-hash caching: reuse the stored
        #     facts for any file whose content and analyzer version are
        #     unchanged since the last run, instead of re-parsing it. ---
        existing_files = {f.path: f for f in db.query(FileModel).filter(FileModel.repository_id == repo_row.id)}
        seen_paths: set[str] = set()
        files_analyzed = 0
        files_cached = 0
        files_skipped_unreadable = 0
        file_import_data: list[tuple[str, str, list[str]]] = []  # (path, module_prefix, import_targets)

        for rel_path in source_paths:
            full_path = Path(clone_path) / rel_path
            try:
                raw_bytes = full_path.read_bytes()
            except OSError:
                files_skipped_unreadable += 1
                continue
            seen_paths.add(rel_path)
            content_hash = _content_hash(raw_bytes)
            module_prefix = assign_file_to_module(rel_path, module_prefixes)
            module = module_rows.get(module_prefix) if module_prefix else None
            existing = existing_files.get(rel_path)

            if existing and existing.content_hash == content_hash and existing.analyzer_version == ANALYZER_VERSION:
                files_cached += 1
                existing.module_id = module.id if module else None
                file_import_data.append((rel_path, module_prefix or "", existing.import_targets or []))
                continue

            text = raw_bytes.decode("utf-8", errors="ignore")
            facts = analyze_file(rel_path, text)
            files_analyzed += 1
            import_targets = facts.import_targets if facts else []
            file_import_data.append((rel_path, module_prefix or "", import_targets))

            if existing:
                existing.module_id = module.id if module else None
                existing.language = facts.language if facts else None
                existing.size_bytes = len(raw_bytes)
                existing.is_test = facts.is_test if facts else False
                existing.is_config = facts.is_config if facts else False
                existing.complexity = facts.cyclomatic_complexity if facts else 0.0
                existing.doc_coverage_pct = facts.doc_coverage_pct if facts else 0.0
                existing.content_hash = content_hash
                existing.analyzer_version = ANALYZER_VERSION
                existing.import_targets = import_targets
                db.add(existing)
            else:
                db.add(
                    FileModel(
                        repository_id=repo_row.id, module_id=module.id if module else None, path=rel_path,
                        language=facts.language if facts else None, size_bytes=len(raw_bytes),
                        is_test=facts.is_test if facts else False, is_config=facts.is_config if facts else False,
                        complexity=facts.cyclomatic_complexity if facts else 0.0,
                        doc_coverage_pct=facts.doc_coverage_pct if facts else 0.0,
                        content_hash=content_hash, analyzer_version=ANALYZER_VERSION, import_targets=import_targets,
                    )
                )

        # Files that existed before but are no longer on disk were deleted
        # upstream — remove their rows (never deletes Commit/KnowledgeScore/
        # RiskScore history, which reference module_id, not file_id).
        for path, row in existing_files.items():
            if path not in seen_paths:
                db.delete(row)
        db.flush()

        # --- Module dependency auto-extraction from captured imports ---
        edges = resolve_module_dependencies(module_prefixes, file_import_data)
        existing_edges = {
            (e.module_id, e.depends_on_module_id): e
            for e in db.query(ModuleDependency).filter(ModuleDependency.module_id.in_([m.id for m in module_rows.values()]))
        }
        for edge in edges:
            src = module_rows.get(edge.from_module_prefix)
            dst = module_rows.get(edge.to_module_prefix)
            if not src or not dst:
                continue
            key = (src.id, dst.id)
            if key in existing_edges:
                existing_edges[key].weight = edge.weight
                db.add(existing_edges[key])
            else:
                db.add(ModuleDependency(module_id=src.id, depends_on_module_id=dst.id, weight=edge.weight, source="import"))
        db.flush()

        # --- New commits: bulk insert, idempotent-retry-safe ---
        new_commit_hashes = [c.hash for c in commit_records]
        already_present: set[str] = set()
        if new_commit_hashes:
            rows = (
                db.query(Commit.hash)
                .filter(Commit.repository_id == repo_row.id, Commit.hash.in_(new_commit_hashes))
                .all()
            )
            already_present = {r[0] for r in rows}

        module_activity_delta: dict[tuple, dict] = {}  # (dev_id, module_id) -> {commits, lines, last_at}
        commit_rows_to_insert = []
        inserted_count = 0
        for c in commit_records:
            if c.hash in already_present:
                continue  # already ingested by a prior (possibly interrupted) run
            dev = dev_lookup.get((c.author_name or "unknown", c.author_email or None))
            module_changes: dict[str, int] = {}
            total_additions = total_deletions = 0
            for fc in c.files:
                total_additions += fc.insertions
                total_deletions += fc.deletions
                module_prefix = assign_file_to_module(fc.path, module_prefixes)
                if module_prefix:
                    lines = fc.insertions + fc.deletions
                    module_changes[module_prefix] = module_changes.get(module_prefix, 0) + lines

            authored_at = datetime.fromisoformat(c.authored_at_iso)
            commit_rows_to_insert.append(
                Commit(
                    repository_id=repo_row.id, developer_id=dev.id if dev else None, hash=c.hash,
                    message=c.message[:2000], authored_at=authored_at,
                    additions=total_additions, deletions=total_deletions,
                    files_changed_count=len(c.files), module_changes=module_changes,
                )
            )
            inserted_count += 1

            if dev:
                for module_prefix, lines in module_changes.items():
                    module = module_rows.get(module_prefix)
                    if not module:
                        continue
                    key = (dev.id, module.id)
                    delta = module_activity_delta.setdefault(key, {"commits": 0, "lines": 0, "last_at": authored_at})
                    delta["commits"] += 1
                    delta["lines"] += lines
                    if authored_at > delta["last_at"]:
                        delta["last_at"] = authored_at

        if commit_rows_to_insert:
            db.bulk_save_objects(commit_rows_to_insert)  # single batched insert (perf: see module docstring)

        # --- Upsert DeveloperModuleActivity (cumulative current-state aggregate) ---
        if module_activity_delta:
            existing_activity = {
                (a.developer_id, a.module_id): a
                for a in db.query(DeveloperModuleActivity).filter(
                    DeveloperModuleActivity.developer_id.in_({k[0] for k in module_activity_delta})
                )
            }
            for (dev_id, module_id), delta in module_activity_delta.items():
                existing = existing_activity.get((dev_id, module_id))
                if existing:
                    existing.commits_count += delta["commits"]
                    existing.lines_changed += delta["lines"]
                    existing_last_at = existing.last_activity_at
                    if existing_last_at and existing_last_at.tzinfo is None:
                        existing_last_at = existing_last_at.replace(tzinfo=timezone.utc)
                    if existing_last_at is None or delta["last_at"] > existing_last_at:
                        existing.last_activity_at = delta["last_at"]
                    db.add(existing)
                else:
                    db.add(
                        DeveloperModuleActivity(
                            developer_id=dev_id, module_id=module_id,
                            commits_count=delta["commits"], lines_changed=delta["lines"],
                            last_activity_at=delta["last_at"],
                        )
                    )

        # --- Update repository summary + incremental-indexing checkpoint ---
        repo_row.total_files = len(seen_paths)
        repo_row.contributor_count = db.query(Developer).filter(Developer.project_id == repo_row.project_id).count()
        repo_row.commit_count = db.query(Commit).filter(Commit.repository_id == repo_row.id).count() + inserted_count
        repo_row.last_analyzed_at = datetime.now(timezone.utc).isoformat()
        repo_row.last_indexed_commit_sha = head_sha
        repo_row.last_indexed_branch = current_branch
        repo_row.scan_mode = scan_mode
        db.add(repo_row)
        db.commit()

        return {
            "developers": len(dev_lookup and {d.id for d in dev_lookup.values()}),
            "modules": len(module_rows),
            "files_total": len(seen_paths),
            "files_analyzed": files_analyzed,
            "files_cached": files_cached,
            "files_skipped_unreadable": files_skipped_unreadable,
            "commits_fetched": len(commit_records),
            "commits_inserted": inserted_count,
            "commits_already_present": len(already_present),
            "dependency_edges": len(edges),
            "incremental": can_resume,
        }
    finally:
        cleanup_clone(clone_path, was_local=is_local)
