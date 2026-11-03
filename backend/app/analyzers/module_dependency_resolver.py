"""
Automatic module-dependency extraction from captured source imports (master
spec §7). Heuristic by design: resolving an import string to an internal
module is inherently fuzzy across languages/build systems, so a missed or
spurious edge only weakens a dependency-risk signal — it never corrupts a
risk score outright (dependency_risk is one of six weighted factors).
"""
import posixpath
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DependencyEdge:
    from_module_prefix: str
    to_module_prefix: str
    weight: float


@dataclass
class ExternalLibrary:
    name: str
    file_count: int
    used_by_modules: list[str]


def _resolve_target_path(raw: str, importing_file_path: str) -> str:
    """
    Resolves one captured import string to a repo-relative path:
    - relative (starts with '.' or '..', JS/TS/Go style): resolved against
      the importing file's own directory, e.g. "../billing/invoice" from
      "src/checkout/flow.js" -> "src/billing/invoice".
    - absolute dotted (Python style, e.g. "src.payment.gateway"): dots
      become slashes.
    - everything else (bare package names like "os", "react"): returned
      as-is; these simply won't match any internal module_prefix, which is
      correct — they're external dependencies, not internal module edges.
    """
    if raw.startswith(("./", "../")) or raw == "." or raw == "..":
        file_dir = posixpath.dirname(importing_file_path)
        joined = posixpath.normpath(posixpath.join(file_dir, raw))
        return joined.lstrip("/")
    if "/" not in raw and "." in raw:
        return raw.replace(".", "/")
    return raw


def resolve_module_dependencies(
    module_prefixes: list[str],
    file_module_and_imports: list[tuple[str, str, list[str]]],  # (file_path, its module_prefix, raw import targets)
    min_edge_weight: int = 1,
) -> list[DependencyEdge]:
    """
    Returns deduplicated edges with weight = number of distinct importing
    files that produced that edge (a simple, explainable confidence signal).
    """
    sorted_prefixes = sorted(module_prefixes, key=len, reverse=True)

    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    for file_path, file_module, raw_imports in file_module_and_imports:
        if not file_module:
            continue
        for raw in raw_imports:
            resolved = _resolve_target_path(raw, file_path)
            if not resolved:
                continue
            target_module = next(
                (p for p in sorted_prefixes if resolved == p or resolved.startswith(p + "/")),
                None,
            )
            if target_module and target_module != file_module:
                edge_counts[(file_module, target_module)] += 1

    return [
        DependencyEdge(from_module_prefix=src, to_module_prefix=dst, weight=float(count))
        for (src, dst), count in edge_counts.items()
        if count >= min_edge_weight
    ]


def _normalize_external_name(raw: str) -> str | None:
    """Reduces a raw import string to a displayable external package name.

    Returns None for strings that are clearly relative/internal fragments
    rather than real third-party packages.
    """
    s = raw.strip()
    if not s:
        return None
    # Relative imports resolve internally (or are unresolvable fragments).
    if s.startswith("."):
        return None
    # Scoped npm packages: "@scope/name/..." -> "@scope/name".
    if s.startswith("@"):
        parts = s.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else s
    # Dotted (python) or slashed (js/go) paths: first segment is the package.
    first = s.replace("\\", "/").split("/")[0].split(".")[0]
    first = first.strip()
    if not first or first in {"/"}:
        return None
    return first


def extract_external_libraries(
    module_prefixes: list[str],
    file_module_and_imports: list[tuple[str, str, list[str]]],  # (file_path, its module_prefix, raw import targets)
    max_libraries: int = 30,
) -> list[ExternalLibrary]:
    """Derives genuinely-third-party dependencies from the same captured
    import strings the internal-edge resolver uses: any import that does NOT
    resolve to an internal module prefix is attributed to an external package.

    No invented data — only what the analyzers actually captured in source.
    """
    sorted_prefixes = sorted(module_prefixes, key=len, reverse=True)
    by_lib: dict[str, set[str]] = defaultdict(set)  # lib -> importing file paths
    lib_modules: dict[str, set[str]] = defaultdict(set)  # lib -> importing module prefixes

    for file_path, file_module, raw_imports in file_module_and_imports:
        for raw in raw_imports:
            resolved = _resolve_target_path(raw, file_path)
            if not resolved:
                continue
            internal = next(
                (p for p in sorted_prefixes if resolved == p or resolved.startswith(p + "/")),
                None,
            )
            if internal:
                continue
            name = _normalize_external_name(raw)
            if not name:
                continue
            by_lib[name].add(file_path)
            if file_module:
                lib_modules[name].add(file_module)

    ranked = sorted(by_lib.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:max_libraries]
    return [
        ExternalLibrary(name=name, file_count=len(paths), used_by_modules=sorted(lib_modules[name]))
        for name, paths in ranked
    ]
