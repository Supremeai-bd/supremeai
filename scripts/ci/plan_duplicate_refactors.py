#!/usr/bin/env python3
"""Generate a safe, reviewable refactoring plan for duplicate code.

The planner intentionally does not delete, move, or rewrite source files. It
turns the duplication inventory produced by the repository audit into actions
that can be reviewed and executed in small PRs:

* exact duplicate files -> choose a tentative canonical owner and inspect refs;
* exact duplicate Python functions -> extract/shared-helper candidates;
* AST/token clones -> manual refactor candidates;
* schema, generated, test, example, and mirror copies -> SSOT/regeneration work,
  not blind deletion.

Example:
    python scripts/ci/plan_duplicate_refactors.py \
      --inventory duplication-inventory.json \
      --output duplicate-refactor-plan.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


@dataclass
class FilePlan:
    group: list[str]
    category: str
    confidence: str
    canonical_candidate: str
    duplicate_candidates: list[str]
    reference_counts: dict[str, int]
    action: str
    verification: list[str]


@dataclass
class MethodPlan:
    group: list[str]
    category: str
    confidence: str
    action: str
    verification: list[str]


def args_parser(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--output", type=Path, default=Path("duplicate-refactor-plan.md"))
    p.add_argument("--json-output", type=Path, default=None)
    p.add_argument("--include-archive", action="store_true")
    p.add_argument("--min-clone-lines", type=int, default=20)
    return p.parse_args(argv)


def is_archive(path: str) -> bool:
    return path.startswith("archive/") or "/archive/" in path


def active_path(path: str) -> bool:
    return not is_archive(path) and "__pycache__" not in path and "node_modules" not in path


def path_score(path: str) -> int:
    """Score only; this is a proposal, never an automatic ownership decision."""
    score = 0
    if path.startswith(("src/", "core/", "skills/", "browser/", "gateway/", "studio/")):
        score += 30
    if path.startswith("scripts/ops/"):
        score += 25
    if path.startswith("scripts/"):
        score += 15
    if "/generated/" in path or path.startswith("generated/"):
        score -= 30
    if "/tests/" in path or path.startswith("tests/") or "/test" in Path(path).name:
        score -= 40
    if path.startswith(("examples/", ".agents/")):
        score -= 25
    if "/archive/" in path or path.startswith("archive/"):
        score -= 100
    if re.search(r"(?:_20\d{2}|\.bak|\.old|copy|duplicate)", path, re.I):
        score -= 25
    return score


def category(paths: Iterable[str]) -> str:
    joined = " ".join(paths).lower()
    if any(is_archive(p) for p in paths):
        return "archive/history"
    if "/generated/" in joined or "schema" in joined or "fixture" in joined:
        return "generated/schema mirror"
    if any("test" in Path(p).name.lower() or "/tests/" in p for p in paths):
        return "test mirror"
    if any(p.startswith("examples/") or "/examples/" in p for p in paths):
        return "example mirror"
    if any(p.startswith(".github/") for p in paths) and any(p.startswith("core/github/") for p in paths):
        return "governance mirror"
    if any(p.startswith("browser/") for p in paths) and any(p.startswith("core/browser/") for p in paths):
        return "browser/core mirror"
    if any(p.startswith("api-schemas/") for p in paths) and any("gateway/contracts" in p for p in paths):
        return "contract mirror"
    if any(p.startswith("skills/") for p in paths) and any("core/skills" in p or "gateway/skills" in p for p in paths):
        return "skills mirror"
    return "active implementation duplicate"


def tracked_text_files(root: Path) -> list[tuple[str, str]]:
    try:
        names = subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        names = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    result = []
    for name in names:
        path = root / name
        if not path.is_file() or is_archive(name) or "__pycache__" in name:
            continue
        try:
            result.append((name, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return result


def reference_counts(paths: list[str], files: list[tuple[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for target in paths:
        counts[target] = sum(1 for name, text in files if name != target and target in text)
    return counts


def build_file_plans(inventory: dict[str, Any], root: Path, include_archive: bool) -> list[FilePlan]:
    files = tracked_text_files(root)
    plans: list[FilePlan] = []
    for group in inventory.get("exact_file_groups", []):
        group = [str(x) for x in group]
        if not include_archive:
            group = [p for p in group if active_path(p)]
        if len(group) < 2:
            continue
        group = sorted(group, key=lambda p: (-path_score(p), len(p), p))
        kind = category(group)
        canonical = group[0]
        duplicates = group[1:]
        refs = reference_counts(group, files)
        if kind in {"contract mirror", "generated/schema mirror", "governance mirror", "browser/core mirror", "skills mirror", "test mirror", "example mirror"}:
            confidence = "review"
            action = "Choose one SSOT and replace the other copy with generation, sync, or a thin compatibility wrapper; do not delete blindly."
            verification = ["Confirm which path is packaged/deployed.", "Find the generator or synchronization job.", "Add a parity test and document the ownership rule."]
        else:
            confidence = "high" if max(refs.values(), default=0) == 0 else "medium"
            action = "Keep the canonical candidate, update imports/callers, then delete or wrapperize the duplicate candidates."
            verification = ["Search imports, workflows, Dockerfiles, manifests, and deployment configs.", "Run the owning unit/integration tests.", "Run the duplicate detector again after consolidation."]
        plans.append(FilePlan(group, kind, confidence, canonical, duplicates, refs, action, verification))
    return plans


def method_display(item: dict[str, Any]) -> str:
    return f"{item.get('file')}:{item.get('line')} `{item.get('name')}`"


def build_method_plans(inventory: dict[str, Any], min_lines: int) -> list[MethodPlan]:
    plans: list[MethodPlan] = []
    for key, title in (("python_exact_function_groups", "exact Python method"), ("python_semantic_function_groups", "near-identical Python method")):
        for group in inventory.get(key, []):
            entries = [x for x in group if active_path(str(x.get("file", "")))]
            if len(entries) < 2:
                continue
            names = [method_display(x) for x in entries]
            if title.startswith("exact"):
                action = "Extract one shared helper or move the canonical method; retain compatibility wrappers only where callers require the old API."
                confidence = "high"
            else:
                action = "Compare inputs, side effects, exceptions, and return contracts; extract only the common behavior, not merely similar syntax."
                confidence = "review"
            plans.append(MethodPlan(names, title, confidence, action, ["Add focused tests for both callers.", "Compare output and error behavior before and after extraction.", "Use type checking/linting and run affected tests."]))
    return plans


def build_clone_plans(inventory: dict[str, Any], min_lines: int) -> list[dict[str, Any]]:
    rows = []
    for key in ("jscpd_exact_active", "jscpd_ast_similar_active"):
        for item in inventory.get(key, []):
            if int(item.get("lines", 0)) < min_lines:
                continue
            rows.append({"kind": key, **item})
    rows.sort(key=lambda x: (-int(x.get("lines", 0)), -int(x.get("tokens", 0))))
    return rows


def render(plan_files: list[FilePlan], plan_methods: list[MethodPlan], clones: list[dict[str, Any]], inventory: Path) -> str:
    lines = ["# Duplicate Refactoring Plan", "", f"Source inventory: `{inventory}`", "", "## Safety rules", "", "- This plan is advisory and does not modify source files.", "- Do not merge mirrors until the canonical owner and regeneration/sync mechanism are documented.", "- Preserve public import paths with a wrapper when external consumers may depend on them.", "- Require parity tests for behavior-preserving extractions and schema/generated-file changes.", "", "## File-level refactors", ""]
    for i, item in enumerate(plan_files, 1):
        lines += [f"### F{i}. {item.category} — {item.confidence} confidence", "", f"**Tentative canonical:** `{item.canonical_candidate}`", "", "**Duplicate candidates:**"]
        lines += [f"- `{p}` (active references found: {item.reference_counts.get(p, 0)})" for p in item.duplicate_candidates]
        lines += ["", f"**Group:** " + " ↔ ".join(f"`{p}`" for p in item.group), "", f"**Action:** {item.action}", "", "**Verification:**"]
        lines += [f"- {v}" for v in item.verification] + [""]
    lines += ["## Method-level refactors", ""]
    for i, item in enumerate(plan_methods, 1):
        lines += [f"### M{i}. {item.category} — {item.confidence} confidence", "", "**Candidates:**"]
        lines += [f"- {x}" for x in item.group] + ["", f"**Action:** {item.action}", "", "**Verification:"]
        lines += [f"- {v}" for v in item.verification] + [""]
    lines += ["## Large token/AST clone records", "", "These are lower-level regions that may be covered by the file/method plans above. Full records remain in the inventory JSON.", "", "| Lines | Tokens | Kind | File A | Range | File B | Range |", "|---:|---:|---|---|---:|---|---:|"]
    for item in clones:
        lines.append(f"| {item.get('lines')} | {item.get('tokens')} | {item.get('kind')} | `{item.get('file_a')}` | {item.get('start_a')}-{item.get('end_a')} | `{item.get('file_b')}` | {item.get('start_b')}-{item.get('end_b')} |")
    lines += ["", "## Suggested execution order", "", "1. Start with active implementation duplicates with zero references to the secondary path.", "2. Consolidate shared helpers for exact method groups and add behavior tests.", "3. Resolve runtime/gateway/browser/skills ownership before touching mirrors.", "4. Convert schema/generated copies to a generator or parity guard.", "5. Apply one domain per PR, run CI, and rerun `detect_new_duplicates.py`.", ""]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = args_parser(argv)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    file_plans = build_file_plans(inventory, args.repo_root, args.include_archive)
    method_plans = build_method_plans(inventory, args.min_clone_lines)
    clone_plans = build_clone_plans(inventory, args.min_clone_lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(file_plans, method_plans, clone_plans, args.inventory) + "\n", encoding="utf-8")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps({"file_plans": [asdict(x) for x in file_plans], "method_plans": [asdict(x) for x in method_plans], "clone_plans": clone_plans}, indent=2) + "\n", encoding="utf-8")
    print(f"file_plans={len(file_plans)} method_plans={len(method_plans)} clone_records={len(clone_plans)}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
