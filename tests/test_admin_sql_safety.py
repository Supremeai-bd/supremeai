"""ISSUE-1588 regression tests — no hand-rolled f-string SQL identifiers in admin.py.

The backup quick-action must:
  1. validate table names against the strict ``^[A-Za-z0-9_]{1,64}$`` pattern
     (rejects quotes, spaces, unicode trickery, dotted names, ...);
  2. quote identifiers via SQLAlchemy's dialect ``identifier_preparer`` —
     the canonical, injection-proof mechanism for non-bindable identifiers;
  3. never contain the banned hand-quoted ``text(f'SELECT * FROM "..."'`` pattern.
"""

from __future__ import annotations

import re
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
_ADMIN = _BACKEND / "api" / "routes" / "admin.py"


def test_table_name_pattern_rejects_injection_shapes():
    pattern = re.compile(r"^[A-Za-z0-9_]{1,64}$")
    bad = [
        'users"; DROP TABLE users; --',  # classic injection
        "us\u00e9rs",  # unicode trickery
        "user table",  # space
        'user"table',  # embedded quote
        "user`table",  # backtick
        "user$table",  # dollar (not in charset)
        "",  # empty
        "a" * 65,  # too long
    ]
    for name in bad:
        assert pattern.match(name) is None, f"pattern must reject {name!r}"
    for name in ("users", "agent_tasks", "A1_b2", "x"):
        assert pattern.match(name) is not None, f"pattern must accept {name!r}"


def test_admin_backup_uses_dialect_identifier_preparer():
    source = _ADMIN.read_text(encoding="utf-8")
    assert "identifier_preparer" in source, (
        "must quote identifiers via the dialect preparer"
    )
    assert "quoted_name" not in source, "manual quoted_name f-string pattern removed"


def test_admin_has_no_hand_quoted_fstring_table_sql():
    source = _ADMIN.read_text(encoding="utf-8")
    banned = "text(f'SELECT * FROM \""
    assert banned not in source, (
        "hand-rolled quoted f-string SQL is banned (issue #1588)"
    )
    # the surviving f-string SQL must interpolate ONLY a preparer-quoted identifier
    import re as _re

    for match in _re.finditer(r"text\(f[\"']SELECT \* FROM \{([^}]+)\}", source):
        assert match.group(1).strip() == "safe_table", (
            "only the preparer-quoted ident may be interpolated"
        )
