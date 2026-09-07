from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/generated/module_capability_matrix.json"


def classify(path: Path, source: str) -> str:
    text = path.as_posix()
    if "/tests/" in text or text.startswith("tests/"):
        return "test"
    if "adapter" in path.stem or "integration" in text or "mcp" in text:
        return "adapter"
    if "registry" in path.stem or "router" in path.stem or "service" in path.stem:
        return "canonical"
    if "worker" in text or "agent" in text:
        return "dormant_or_dynamic"
    return "human_review"


def python_entrypoints(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"main", "create_app", "get_app", "health", "register"}:
            names.append(node.name)
    return sorted(set(names))


def build() -> dict:
    modules = []
    excluded_parts = {".git", "node_modules", ".vite", "dist", "build", "coverage", "__pycache__", ".next", "target"}
    for base in (ROOT / "backend", ROOT / "frontend", ROOT / "infrastructure", ROOT / "scripts"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if any(part in excluded_parts for part in path.parts):
                continue
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            rel = path.relative_to(ROOT).as_posix()
            source = path.read_text(encoding="utf-8", errors="ignore")
            modules.append({
                "path": rel,
                "kind": path.suffix[1:],
                "classification": classify(path, source),
                "entrypoints": python_entrypoints(path) if path.suffix == ".py" else [],
                "capability_signals": sorted({word for word in ("capability", "register", "dispatch", "execute", "health", "memory", "browser", "mcp", "realtime") if word in source.lower()}),
            })
    return {"schema_version": "1.0", "source": "main", "module_count": len(modules), "modules": modules}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
