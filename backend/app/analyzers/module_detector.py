"""
Module detection: infers modules from top-level source directories.

Heuristic, documented as such (docs/analysis-methodology.md §2). A file
maps to at most one module by longest-matching path prefix.
"""
from pathlib import PurePosixPath

EXCLUDED_DIR_NAMES = {
    "node_modules", "dist", "build", ".venv", "venv", "vendor",
    "__pycache__", ".git", "target", "bin", "obj", ".next", "coverage",
}


def infer_module_prefixes(file_paths: list[str], depth: int = 2) -> list[str]:
    """
    Returns a sorted list of candidate module path prefixes, e.g.
    ["src/auth", "src/payment", "src/orders"] for depth=2 with a "src/" root,
    or ["auth", "payment"] for depth=1 flat layouts.
    """
    prefixes: set[str] = set()
    for raw in file_paths:
        parts = [p for p in PurePosixPath(raw).parts[:-1] if p not in EXCLUDED_DIR_NAMES]
        if not parts:
            continue
        # Skip a generic single top-level container (e.g. "src", "lib") by using
        # one extra depth level when the first segment is a common container name.
        container_names = {"src", "lib", "app", "packages"}
        start = 1 if parts[0] in container_names and len(parts) > 1 else 0
        candidate_parts = parts[start:start + depth]
        if candidate_parts:
            prefixes.add("/".join(parts[: start + len(candidate_parts)]))
    return sorted(prefixes)


def assign_file_to_module(file_path: str, module_prefixes: list[str]) -> str | None:
    """Longest-prefix match; returns None if the file doesn't belong to any detected module."""
    best: str | None = None
    for prefix in module_prefixes:
        if file_path.startswith(prefix + "/") or file_path == prefix:
            if best is None or len(prefix) > len(best):
                best = prefix
    return best


def module_display_name(prefix: str) -> str:
    return PurePosixPath(prefix).name or prefix
