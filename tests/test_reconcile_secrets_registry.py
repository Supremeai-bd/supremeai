"""#4092 — secrets-registry Actions-surface gate regression tests (P6).

Defect class: **governance-gate surface gap** — reconcile_secrets_registry.py
শুধু code env-usage দেখত; `.github/workflows/**`-এর `secrets.<NAME>` সারফেস
SSOT-এ অদৃশ্য ছিল (৫৩ unique ref, ২৬ unclassified — একই drift-ক্লাস যা
#3774-কে টিকিয়ে রেখেছিল)।

এই টেস্ট-বান্ডেল চুক্তি মেশিন-এনফোর্সড রাখে:
  1. Real tree: প্রতিটি Actions secrets ref-এর registry row আছে (strict-green)
  2. Negative: নিবন্ধিত-বিহীন planted `secrets.X` gate-কে ধরবে (অন্ধ হলে লাল)
  3. GITHUB_TOKEN automatic-token exclusion অক্ষত
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import yaml  # noqa: E402

from reconcile_secrets_registry import (  # noqa: E402
    REGISTRY,
    classify_actions_secrets,
    discover_actions_secrets,
    load_registry_names,
)


# ─────────────────────────────────────────────────────── 1: real-tree contract
def test_all_actions_secrets_registered_on_main():
    """#4092 acceptance: unclassified Actions secrets = 0 (strict-green SSOT)।"""
    actions = discover_actions_secrets()
    registered = load_registry_names()
    unclassified = classify_actions_secrets(actions, registered)
    assert unclassified == {}, (
        "unregistered Actions secrets resurfaced: "
        f"{sorted(unclassified)} — add registry rows (#4092 contract)"
    )
    assert len(actions) >= 50, (
        "Actions-surface discovery collapsed — scanner regression"
    )


def test_registry_rows_carry_criticality():
    """নতুন row-গুলোও বাকি registry-র মতোই classified (criticality map বাধ্যতামূলক)।"""
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    rows = {r["name"]: r for r in data.get("keys", []) if r.get("name")}
    for name in ("SELF_HEAL_PAT", "QA_ADMIN_PASSWORD", "RENDER_WORKER_SVC_ID",
                 "FIREBASE_TOKEN", "DATABASE_URL"):
        assert name in rows, f"#4092 registry row missing: {name}"
        assert rows[name].get("criticality"), f"{name}: criticality map required"


# ───────────────────────────────────────────────── 2: negative (planted ref)
def test_unregistered_planted_secret_is_caught(tmp_path):
    """নিবন্ধিত-বিহীন planted `secrets.X` gate-এ ধরা পড়বে — negative proof।"""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "fake.yml").write_text(
        "steps:\n"
        "  - run: curl -H \"Auth: Bearer ${{ secrets.TOTALLY_UNREGISTERED_KEY }}\"\n",
        encoding="utf-8",
    )
    actions = discover_actions_secrets(root=tmp_path)
    assert "TOTALLY_UNREGISTERED_KEY" in actions, "planted ref not discovered"
    unclassified = classify_actions_secrets(actions, set())
    assert "TOTALLY_UNREGISTERED_KEY" in unclassified, (
        "gate is BLIND to unregistered Actions secrets — #4092 class alive"
    )


def test_registered_planted_secret_passes(tmp_path):
    """Registry-row-যুক্ত planted ref ফ্ল্যাগ হয় না (over-suppression guard)।"""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "fake.yml").write_text(
        "steps:\n"
        "  - run: deploy --token ${{ secrets.SELF_HEAL_PAT }}\n",
        encoding="utf-8",
    )
    registered = load_registry_names()
    actions = discover_actions_secrets(root=tmp_path)
    unclassified = classify_actions_secrets(actions, registered)
    assert "SELF_HEAL_PAT" not in unclassified


# ─────────────────────────────────────────────────────── 3: noise exclusions
def test_github_token_automatic_exclusion():
    """secrets.GITHUB_TOKEN = automatic token — noise, registry-row লাগে না।"""
    registered = load_registry_names()
    actions = {"GITHUB_TOKEN": ["w.yml"], "SELF_HEAL_PAT": ["w.yml"]}
    unclassified = classify_actions_secrets(actions, registered)
    assert "GITHUB_TOKEN" not in unclassified
