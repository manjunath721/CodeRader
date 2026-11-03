"""
Common interface every per-language source analyzer implements (master spec
§6, architecture.md §6). Adding a language means implementing this
interface and registering it in registry.py — nothing else changes.
"""
from dataclasses import dataclass, field


@dataclass
class FileFacts:
    language: str
    function_count: int = 0
    class_count: int = 0
    cyclomatic_complexity: float = 0.0
    import_count: int = 0
    comment_lines: int = 0
    code_lines: int = 0
    todo_count: int = 0
    is_test: bool = False
    is_config: bool = False
    # Raw import/module targets (e.g. "src.payment.gateway", "./billing"), used
    # by the module-dependency resolver to auto-detect inter-module edges.
    # Heuristic and best-effort — see base of CFamilyAnalyzer for caveats.
    import_targets: list = field(default_factory=list)

    @property
    def doc_coverage_pct(self) -> float:
        total = self.comment_lines + self.code_lines
        if total == 0:
            return 0.0
        return round(100 * self.comment_lines / total, 2)


class LanguageAnalyzer:
    """Base interface. Subclasses implement `parse`."""

    extensions: tuple[str, ...] = ()

    def parse(self, file_text: str, file_path: str) -> FileFacts:  # pragma: no cover - interface
        raise NotImplementedError
