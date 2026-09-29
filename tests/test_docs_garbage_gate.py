# বাংলা মন্তব্য: Zero-Garbage Docs Gate পিন-টেস্ট (#2450)।
# docs/ স্প্রল 'GitHub Issues as Live Operational Truth' দর্শনের পরিপন্থী —
# এই টেস্টগুলো গেটের অস্তিত্ব, rules.yml পলিসি ও গেট-লজিকের সঠিকতা পিন করে রাখে।

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATES_PATH = ROOT / ".github/scripts/constitution/gates.py"
RULES_PATH = ROOT / ".github/constitution/rules.yml"


def _load_gates_module():
    # বাংলা মন্তব্য: .github/scripts প্যাকেজ-পাথে নেই, তাই spec দিয়ে লোড করা হয়।
    spec = importlib.util.spec_from_file_location("constitution_gates_under_test", GATES_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("constitution_gates_under_test", mod)
    spec.loader.exec_module(mod)
    return mod


def _policies() -> dict:
    mod = _load_gates_module()
    return mod.load_policies(RULES_PATH)


def test_docs_garbage_policy_registered() -> None:
    # বাংলা মন্তব্য: rules.yml-এ পলিসি থাকতে হবে — allowlist ছাড়া গেট অন্ধ।
    policies = _policies()
    policy = policies.get("docs_garbage_policy") or {}
    assert policy.get("non_allowlisted_new_docs") == "block"
    patterns = policy.get("allowed_patterns") or []
    assert any("master_docs" in p for p in patterns), "master_docs allowlist-এ নেই"
    assert any(p.endswith("docs/INDEX.md") for p in patterns), "INDEX.md allowlist-এ নেই"


def test_gate_wired_in_cli_choices() -> None:
    # বাংলা মন্তব্য: gates.py CLI choices ও dispatch-এ docs_garbage থাকতে হবে।
    source = GATES_PATH.read_text(encoding="utf-8")
    assert '"docs_garbage"' in source, "CLI choices-এ docs_garbage নেই"
    assert 'policies.get("docs_garbage_policy")' in source, "dispatch-এ পলিসি রিডিং নেই"


def test_gate_blocks_new_md_outside_allowlist() -> None:
    mod = _load_gates_module()
    policy = _policies()["docs_garbage_policy"]
    # বাংলা মন্তব্য: gh_api মক — allowlist-বাহির্ভূত নতুন .md দিয়ে।
    mod.gh_api = lambda endpoint, token=None: [
        {"filename": "docs/random-notes/foo.md", "status": "added", "patch": "+ হ্যালো"},
    ]
    rc = mod.run_docs_garbage_gate(0, policy)
    assert rc != 0, "allowlist-বাহির্ভূত নতুন docs .md BLOCK হওয়াই চুক্তি"


def test_gate_allows_allowlisted_and_modified_files() -> None:
    mod = _load_gates_module()
    policy = _policies()["docs_garbage_policy"]
    mod.gh_api = lambda endpoint, token=None: [
        {"filename": "docs/master_docs/ARCH-01-MASTER_CONSTITUTION.md", "status": "added", "patch": "+ x"},
        {"filename": "docs/INDEX.md", "status": "added", "patch": "+ y"},
        {"filename": "docs/plans/ARCH-LIVING-PIPELINE-01-IMPL.md", "status": "modified", "patch": "+ z"},
        {"filename": "backend/core/kernel.py", "status": "added", "patch": "+ code"},
    ]
    rc = mod.run_docs_garbage_gate(0, policy)
    assert rc == 0, "allowlist-ভুক্ত/modified/নন-docs ফাইলে গেট লাল হওয়া ভুল"


def test_archive_and_index_artifacts_exist() -> None:
    # বাংলা মন্তব্য: prune-এর দুই প্রধান আর্টিফ্যাক্ট — আর্কাইভ ও একক ইনডেক্স।
    archive = ROOT / "archives/legacy-docs-2026-09-28.tar.gz"
    assert archive.exists() and archive.stat().st_size > 100_000, "লিগ্যাসি আর্কাইভ অনুপস্থিত"
    index = ROOT / "docs/INDEX.md"
    assert index.exists(), "docs/INDEX.md অনুপস্থিত"
    canon = ROOT / "docs/plans/ARCH-LIVING-PIPELINE-01-IMPL.md"
    assert canon.exists(), "AGENTS.md §12-referenced ক্যানোনিকাল রোডম্যাপ অনুপস্থিত — ref ভাঙল!"
