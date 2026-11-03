"""P0 — Live env/secrets evidence matrix drift guard.

বাংলা: লাইভ এনভায়রনমেন্ট/সিক্রেট এভিডেন্স ম্যাট্রিক্সের ড্রিফট গার্ড —

`docs/deployment/ENV_EVIDENCE_MATRIX.md` (Variable → Source → Required? →
Service → Verified? → Date) হলো প্রোডাকশন সাইন-অফের লাইভ এভিডেন্স। এই টেস্ট
নিশ্চিত করে যে ম্যাট্রিক্স canonical registry
(`backend/core/config_classification.py`) এর সাথে সিঙ্কে আছে:

1. প্রতিটি `required` স্পেক এবং প্রতিটি condition-bearing `conditional`
   স্পেক (required_when সহ) ম্যাট্রিক্সে উল্লেখ থাকতে হবে — registry-তে নতুন
   required ভেরিয়েবল যোগ হলে ম্যাট্রিক্স রো ছাড়া CI ফেইল করবে।
2. Verified কলামে ✅/🟡/⬜ ভোকাবুলারি থাকতে হবে (খালি বা অজানা মার্কার নয়)।
3. ✅ verified-live রো-তে YYYY-MM-DD তারিখ থাকতে হবে।
4. Registry হঠাৎ ছোট হয়ে গেলে (guard-voiding) টেস্ট ফেইল করবে।

আরও দেখুন: docs/deployment/ENV_EVIDENCE_MATRIX.md §6, §5 (owner pending)।
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "docs" / "deployment" / "ENV_EVIDENCE_MATRIX.md"
REGISTRY = REPO_ROOT / "backend" / "core" / "config_classification.py"

# Verification vocabulary locked by the matrix header (§ verification levels).
VERIFICATION_MARKERS = ("✅", "🟡", "⬜")

# Guard-voiding floor: the registry must stay at least this large. If the
# owner intentionally slims the registry, bump these floors in the same PR.
MIN_TOTAL_SPECS = 250
MIN_REQUIRED_SPECS = 30


def _load_registry():
    """Load config_classification.py standalone (metadata-only module)."""
    spec = importlib.util.spec_from_file_location("supremeai_config_classification", REGISTRY)
    assert spec is not None and spec.loader is not None, f"Unable to load {REGISTRY}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _doc_text() -> str:
    return MATRIX.read_text(encoding="utf-8")


def _matrix_variable_tokens(doc: str) -> set[str]:
    """Backtick-quoted UPPER_SNAKE variable names mentioned anywhere in the doc."""
    return set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", doc))


def _table_rows(doc: str) -> list[list[str]]:
    """Markdown table rows as cell lists (header/separator rows excluded)."""
    rows = []
    for line in doc.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue  # separator row
        rows.append(cells)
    return rows


# ---------------------------------------------------------------------------
# Registry floor — silent guard-voiding protection
# ---------------------------------------------------------------------------


def test_registry_meets_size_floor():
    registry = _load_registry()
    specs = registry.CONFIG_SPECS
    assert len(specs) >= MIN_TOTAL_SPECS, (
        f"config registry shrank to {len(specs)} specs (<{MIN_TOTAL_SPECS}); "
        "if intentional, bump MIN_TOTAL_SPECS and re-check matrix coverage"
    )
    required = [s for s in specs if "required" in {c.value for c in s.classes}]
    assert len(required) >= MIN_REQUIRED_SPECS, (
        f"required spec count fell to {len(required)} (<{MIN_REQUIRED_SPECS})"
    )


# ---------------------------------------------------------------------------
# Coverage: every required + condition-bearing conditional spec has a row
# ---------------------------------------------------------------------------


def test_required_specs_covered_by_matrix():
    registry = _load_registry()
    doc = _doc_text()
    tokens = _matrix_variable_tokens(doc)
    required = [s for s in registry.CONFIG_SPECS if "required" in {c.value for c in s.classes}]
    missing = sorted(s.name for s in required if s.name not in tokens)
    assert not missing, (
        "required variables missing from docs/deployment/ENV_EVIDENCE_MATRIX.md: "
        f"{missing}. Add a row (Variable → Source → Required? → Service → "
        "Verified? → Date) — 'exists in code' ≠ 'correctly exists in live env'."
    )


def test_condition_bearing_conditional_specs_covered_by_matrix():
    registry = _load_registry()
    doc = _doc_text()
    tokens = _matrix_variable_tokens(doc)
    conditional = [
        s
        for s in registry.CONFIG_SPECS
        if "conditional" in {c.value for c in s.classes} and s.required_when
    ]
    missing = sorted(s.name for s in conditional if s.name not in tokens)
    assert not missing, (
        f"condition-bearing conditional variables missing from the evidence matrix: {missing}"
    )


def test_matrix_does_not_reference_non_registry_cors_names():
    """g47a: the §1 CORS row historically said USER_CORS_ORIGINS, which is not a
    canonical registry name. Backtick-quoted registry-style names in the matrix
    must be registry names, documented aliases, or explicitly exception-listed
    evidence-prose pairings; user-facing aliases belong to prose, not backticks."""
    doc = _doc_text()
    tokens = _matrix_variable_tokens(doc)
    registry = _load_registry()
    allowed = set(registry.BY_NAME) | set(registry.ALIAS_TO_CANONICAL)
    # Documented non-spec names that appear in evidence prose:
    # - DATABASE_URL: operational pairing of SUPABASE_DATABASE_URL_POOLER used
    #   across docker-compose/SQLAlchemy (registry-completeness note for owner)
    # - NEON_DATABASE_URL: vault name recorded as present-in-vault evidence
    # - LLM_PROVIDER_KEYS: grouped nickname used by the boot alert logs
    allowed |= {"DATABASE_URL", "NEON_DATABASE_URL", "LLM_PROVIDER_KEYS"}
    unknown = sorted(t for t in tokens if t not in allowed and not t.startswith(("VITE_", "X_")))
    assert not unknown, f"matrix mentions non-registry variable names: {unknown}"


# ---------------------------------------------------------------------------
# Row discipline: verification vocabulary + date format
# ---------------------------------------------------------------------------


def test_every_matrix_row_uses_verification_vocabulary():
    doc = _doc_text()
    rows = _table_rows(doc)
    # §1-§3 evidence rows have 6 cells; §4 platform rows have 5. All rows that
    # carry a verification cell must use the locked vocabulary markers.
    evidence_rows = [
        r for r in rows if len(r) >= 5 and any(m in "".join(r) for m in VERIFICATION_MARKERS)
    ]
    assert evidence_rows, "evidence matrix tables not found — doc structure changed?"
    for row in evidence_rows:
        joined = " ".join(row)
        assert any(m in joined for m in VERIFICATION_MARKERS), f"row without status marker: {row}"
        for cell in row:
            assert cell != "", f"empty cell in evidence row: {row}"


def test_verified_rows_carry_date():
    doc = _doc_text()
    date_re = re.compile(r"\d{4}-\d{2}-\d{2}")
    for row in _table_rows(doc):
        joined = " ".join(row)
        if "✅" in joined:
            assert date_re.search(joined), (
                f"verified-live (✅) row without a YYYY-MM-DD date: {row}"
            )


def test_verification_dates_not_in_future():
    doc = _doc_text()
    today = date.today()
    for match in re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", doc):
        parsed = date.fromisoformat(match)
        assert parsed <= today, f"evidence date {match} is in the future"


def test_last_pass_headers_present():
    doc = _doc_text()
    assert re.search(r"Last full pass: \*\*\d{4}-\d{2}-\d{2}\*\*", doc), (
        "'Last full pass' header missing or malformed"
    )
    assert re.search(r"Incremental pass: \*\*\d{4}-\d{2}-\d{2}\*\*", doc), (
        "'Incremental pass' header missing — record each re-verification pass"
    )


# ---------------------------------------------------------------------------
# Live-claim spot checks (static anchors for the current pass)
# ---------------------------------------------------------------------------


def test_docs_exposure_row_records_live_404_evidence():
    doc = _doc_text()
    # The docs-policy row must record the live 404 probe, not stay pending.
    docs_row = [
        line
        for line in doc.splitlines()
        if "SUPREMEAI_DOCS_ENABLED" in line and line.strip().startswith("|")
    ]
    assert docs_row, "SUPREMEAI_DOCS_ENABLED row missing from §1"
    row = docs_row[0]
    assert "✅" in row, "docs exposure row should be verified-live (docs default-OFF in production)"
    assert "404" in row and "/openapi.json" in row, (
        "docs exposure row must cite the docs-trio 404 probe evidence"
    )


def test_database_row_records_health_full_evidence():
    doc = _doc_text()
    db_row = [
        line
        for line in doc.splitlines()
        if "SUPABASE_DATABASE_URL_POOLER" in line and line.strip().startswith("|")
    ]
    assert db_row, "database row missing from §1"
    assert "✅" in db_row[0] and "/health/full" in db_row[0], (
        "database row must cite the /health/full per-check live evidence"
    )


def test_frontend_canonical_pair_present():
    doc = _doc_text()
    for name in ("VITE_USER_BACKEND", "VITE_ADMIN_BACKEND"):
        assert f"`{name}`" in doc, f"canonical frontend pair member {name} missing"


def test_registry_alignment_section_present():
    doc = _doc_text()
    assert "## 6. Registry alignment (drift guard)" in doc, (
        "§6 must document the registry-drift-guard contract"
    )
    assert "backend/tests/test_env_evidence_matrix.py" in doc, "§6 must name the enforcing test"
