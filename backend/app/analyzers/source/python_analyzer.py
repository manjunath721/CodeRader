import ast

from app.analyzers.source.base import FileFacts, LanguageAnalyzer

DECISION_NODES = (
    ast.If, ast.For, ast.While, ast.Try, ast.With, ast.BoolOp, ast.ExceptHandler,
)


class PythonAnalyzer(LanguageAnalyzer):
    extensions = (".py",)

    def parse(self, file_text: str, file_path: str) -> FileFacts:
        facts = FileFacts(language="python")
        facts.is_test = "test" in file_path.lower()
        lines = file_text.splitlines()
        facts.code_lines = len([ln for ln in lines if ln.strip() and not ln.strip().startswith("#")])
        facts.comment_lines = len([ln for ln in lines if ln.strip().startswith("#")])
        facts.todo_count = sum(1 for ln in lines if "TODO" in ln or "FIXME" in ln)

        try:
            tree = ast.parse(file_text)
        except SyntaxError:
            return facts

        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                facts.function_count += 1
                # Docstring counts toward documentation even outside comment lines
                if ast.get_docstring(node):
                    facts.comment_lines += 1
            elif isinstance(node, ast.ClassDef):
                facts.class_count += 1
                if ast.get_docstring(node):
                    facts.comment_lines += 1
            elif isinstance(node, ast.Import):
                facts.import_count += 1
                for alias in node.names:
                    facts.import_targets.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                facts.import_count += 1
                if node.module:
                    facts.import_targets.append(("." * node.level) + node.module)
            elif isinstance(node, DECISION_NODES):
                complexity += 1
        facts.cyclomatic_complexity = float(complexity)
        return facts
