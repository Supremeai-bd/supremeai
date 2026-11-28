from __future__ import annotations

import json
import sys
from pathlib import Path

# বাংলা মন্তব্য: core/adaptive_engine/* (ক্যানোনিকাল) এবং লিগ্যাসি backend/adaptive_engine/* উভয় পাথ সমর্থিত
REQUIRED_MODULES = (
    "adaptive_engine/capability_registry.py",
    "adaptive_engine/capability_node.py",
    "adaptive_engine/governed_executor.py",
)


def validate(matrix_path: str) -> dict:
    data = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    modules = data.get("modules", [])
    present = {item["path"] for item in modules}
    missing = sorted(
        f"core/{rel}"
        for rel in REQUIRED_MODULES
        if f"core/{rel}" not in present and f"backend/{rel}" not in present
    )
    return {"ok": not missing, "missing": missing, "module_count": len(modules)}


if __name__ == "__main__":
    result = validate(
        sys.argv[1] if len(sys.argv) > 1 else "docs/generated/module_capability_matrix.json"
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
