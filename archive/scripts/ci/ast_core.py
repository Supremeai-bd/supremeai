#!/usr/bin/env python3
"""
scripts/ci/ast_core.py — SupremeAI Zero-Token AST Parsing Engine powered by Tree-sitter.

Extracts structured syntax trees, functions, classes, and declarations
deterministically without LLM calls or cloud API dependencies.
Compatible with Tree-sitter 0.25+ API.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import tree_sitter_python as tspython
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser, Query, QueryCursor
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False


class SupremeASTEngine:
    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise RuntimeError("Tree-sitter or grammar packages (tree_sitter_python, tree_sitter_typescript) are not installed.")
        
        self.py_lang = Language(tspython.language())
        self.py_parser = Parser(self.py_lang)
        self.py_query = Query(self.py_lang, """
            (function_definition name: (identifier) @name)
            (class_definition name: (identifier) @name)
        """)

        self.ts_lang = Language(tstypescript.language_typescript())
        self.ts_parser = Parser(self.ts_lang)
        self.ts_query = Query(self.ts_lang, """
            (function_declaration name: (identifier) @name)
            (class_declaration name: (type_identifier) @name)
            (method_definition name: (property_identifier) @name)
        """)

    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse source file into structured AST symbols."""
        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": f"File not found: {file_path}", "syntax_valid": False}

        code_bytes = file_path.read_bytes()
        ext = file_path.suffix.lower()

        if ext == ".py":
            tree = self.py_parser.parse(code_bytes)
            return self._extract_symbols(tree, self.py_query, file_path, "python")
        elif ext in [".ts", ".tsx", ".js", ".jsx"]:
            tree = self.ts_parser.parse(code_bytes)
            return self._extract_symbols(tree, self.ts_query, file_path, "typescript")

        return {"error": f"Unsupported language extension: {ext}", "syntax_valid": True}

    def _extract_symbols(self, tree, query: Query, file_path: Path, language: str) -> Dict[str, Any]:
        has_error = tree.root_node.has_error
        functions: List[Dict[str, Any]] = []
        classes: List[Dict[str, Any]] = []

        cursor = QueryCursor(query)
        for pattern_index, captures in cursor.matches(tree.root_node):
            nodes = captures.get("name", [])
            for node in nodes:
                parent = node.parent
                if not parent:
                    continue
                is_class = "class" in parent.type
                symbol_type = "class" if is_class else "function"
                item = {
                    "name": node.text.decode("utf-8", errors="replace"),
                    "type": symbol_type,
                    "file": str(file_path),
                    "start_line": node.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                }
                if is_class:
                    classes.append(item)
                else:
                    functions.append(item)

        return {
            "file": str(file_path),
            "language": language,
            "syntax_valid": not has_error,
            "classes": classes,
            "functions": functions,
            "total_symbols": len(classes) + len(functions),
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SupremeAI Tree-sitter Zero-Token AST Parser")
    parser.add_argument("file", help="Source file path to parse (.py or .ts)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    engine = SupremeASTEngine()
    result = engine.parse_file(Path(args.file))

    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        print(f"File: {result.get('file')}")
        print(f"Language: {result.get('language')}")
        print(f"Syntax Valid: {result.get('syntax_valid')}")
        print(f"Total Symbols: {result.get('total_symbols', 0)}")
        print("\nClasses:")
        for c in result.get("classes", []):
            print(f"  [L{c['start_line']}-L{c['end_line']}] class {c['name']}")
        print("\nFunctions / Methods:")
        for f in result.get("functions", []):
            print(f"  [L{f['start_line']}-L{f['end_line']}] def/fn {f['name']}")


if __name__ == "__main__":
    main()
