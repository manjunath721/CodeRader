"""
Registry mapping file extensions to LanguageAnalyzer instances. To add a
language: implement LanguageAnalyzer.parse and register its extensions here.
"""

# Bump whenever analyzer logic changes in a way that would produce different
# FileFacts for the same source text. The ingestion cache keys on this, so a
# bump invalidates all cached per-file analysis on the next run (perf work).
ANALYZER_VERSION = "3"
from app.analyzers.source.base import FileFacts, LanguageAnalyzer
from app.analyzers.source.cfamily_analyzer import CFamilyAnalyzer
from app.analyzers.source.python_analyzer import PythonAnalyzer

_ANALYZERS: list[LanguageAnalyzer] = [PythonAnalyzer(), CFamilyAnalyzer()]

_EXTENSION_MAP: dict[str, LanguageAnalyzer] = {
    ext: analyzer for analyzer in _ANALYZERS for ext in analyzer.extensions
}


def get_analyzer_for_path(file_path: str) -> LanguageAnalyzer | None:
    if "." not in file_path:
        return None
    ext = "." + file_path.rsplit(".", 1)[-1]
    return _EXTENSION_MAP.get(ext)


def analyze_file(file_path: str, file_text: str) -> FileFacts | None:
    analyzer = get_analyzer_for_path(file_path)
    if analyzer is None:
        return None
    return analyzer.parse(file_text, file_path)


SUPPORTED_EXTENSIONS = tuple(_EXTENSION_MAP.keys())
