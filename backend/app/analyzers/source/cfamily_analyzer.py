import re

from app.analyzers.source.base import FileFacts, LanguageAnalyzer

# Heuristic, regex-based extraction for languages where we don't ship a full
# AST parser in the Python backend (architecture.md §6). Upgradeable to
# tree-sitter later without changing the LanguageAnalyzer interface.

DECISION_KEYWORDS = re.compile(r"\b(if|for|while|case|catch|else if|&&|\|\|)\b")
FUNCTION_PATTERNS = {
    "javascript": re.compile(r"\bfunction\b|=>\s*{|\b\w+\s*\([^)]*\)\s*{"),
    "typescript": re.compile(r"\bfunction\b|=>\s*{|\b\w+\s*\([^)]*\)\s*:\s*\w+\s*{"),
    "java": re.compile(r"\b(public|private|protected|static)[\w\s<>,\[\]]*\s+\w+\s*\([^)]*\)\s*{"),
    "c": re.compile(r"^\s*[\w\*]+\s+\w+\s*\([^;{]*\)\s*{", re.MULTILINE),
    "cpp": re.compile(r"^\s*[\w:<>\*&]+\s+\w+\s*\([^;{]*\)\s*{", re.MULTILINE),
    "go": re.compile(r"\bfunc\s+(\(\w+\s+\*?\w+\)\s+)?\w+\s*\("),
}
CLASS_PATTERNS = re.compile(r"\b(class|struct|interface|type\s+\w+\s+struct)\b")
IMPORT_PATTERNS = re.compile(r"^\s*(import|require\(|#include|using\s+)", re.MULTILINE)
# Best-effort extraction of the imported module/path string itself (not just
# a count) for module-dependency resolution. Deliberately permissive — a
# missed or over-matched import only weakens a dependency edge's confidence,
# it never corrupts a risk score (dependency edges are additive signals).
IMPORT_TARGET_PATTERNS = [
    re.compile(r"""\bimport\s+.*?\bfrom\s+['"]([^'"]+)['"]"""),   # JS/TS: import x from 'y'
    re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),        # JS: require('y')
    re.compile(r"""^\s*import\s+['"]([^'"]+)['"]""", re.MULTILINE),  # JS: bare `import 'y'`
    re.compile(r"""#include\s*["<]([^">]+)[">]"""),                # C/C++
    re.compile(r"""^\s*import\s+\(?\s*["']?([\w./]+)["']?""", re.MULTILINE),  # Go
]
LINE_COMMENT_PREFIXES = ("//",)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class CFamilyAnalyzer(LanguageAnalyzer):
    """Shared heuristic analyzer for JS/TS/Java/C/C++/Go, selected by extension."""

    LANGUAGE_BY_EXT = {
        ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".java": "java",
        ".c": "c", ".h": "c",
        ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
        ".go": "go",
    }
    extensions = tuple(LANGUAGE_BY_EXT.keys())

    def parse(self, file_text: str, file_path: str) -> FileFacts:
        ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
        language = self.LANGUAGE_BY_EXT.get(ext, "unknown")
        facts = FileFacts(language=language)
        facts.is_test = bool(re.search(r"(test|spec)", file_path, re.IGNORECASE))
        facts.is_config = file_path.endswith((".json", ".yml", ".yaml", ".toml"))

        block_comment_matches = BLOCK_COMMENT.findall(file_text)
        block_comment_lines = sum(m.count("\n") + 1 for m in block_comment_matches)
        text_wo_blocks = BLOCK_COMMENT.sub("", file_text)
        lines = text_wo_blocks.splitlines()
        line_comments = len([ln for ln in lines if ln.strip().startswith(LINE_COMMENT_PREFIXES)])
        facts.comment_lines = line_comments + block_comment_lines
        facts.code_lines = len([ln for ln in lines if ln.strip()]) - line_comments
        facts.todo_count = file_text.count("TODO") + file_text.count("FIXME")

        fn_pattern = FUNCTION_PATTERNS.get(language)
        facts.function_count = len(fn_pattern.findall(file_text)) if fn_pattern else 0
        facts.class_count = len(CLASS_PATTERNS.findall(file_text))
        facts.import_count = len(IMPORT_PATTERNS.findall(file_text))
        for pattern in IMPORT_TARGET_PATTERNS:
            facts.import_targets.extend(pattern.findall(file_text))
        facts.cyclomatic_complexity = float(1 + len(DECISION_KEYWORDS.findall(file_text)))
        return facts
