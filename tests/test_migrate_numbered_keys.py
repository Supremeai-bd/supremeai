"""`migrate_numbered_keys.migrate_file` moves reads onto `resolve_numbered_key`.

The numbered-key resolver is what makes a rotation (KEY_1 -> KEY_2) invisible to
callers. The migration must rewrite every direct env read of a family variable,
add the import exactly once, and leave files with nothing to migrate untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import migrate_numbered_keys as migrate  # noqa: E402


def _family():
    assert migrate.FAMILIES, "FAMILIES must not be empty"
    return migrate.FAMILIES[0]


def test_family_reads_are_rewritten_and_import_added(tmp_path):
    fam = _family()
    target = tmp_path / "mod.py"
    target.write_text(
        "import os\n\n"
        f'KEY = os.environ.get("{fam}")\n'
        f'OTHER = os.getenv("{fam}", "")\n',
        encoding="utf-8",
    )
    assert migrate.migrate_file(str(target)) in (0, 1)
    out = target.read_text(encoding="utf-8")
    assert out.count(f'resolve_numbered_key("{fam}")') == 2
    assert migrate.IMPORT_LINE in out


def test_file_without_family_reads_is_untouched(tmp_path):
    target = tmp_path / "clean.py"
    original = "import os\n\nX = os.environ.get('SOMETHING_ELSE')\n"
    target.write_text(original, encoding="utf-8")
    migrate.migrate_file(str(target))
    assert target.read_text(encoding="utf-8") == original


def test_rerun_does_not_duplicate_the_import(tmp_path):
    fam = _family()
    target = tmp_path / "mod.py"
    target.write_text(f"import os\n\nK = os.environ.get(\"{fam}\")\n", encoding="utf-8")
    migrate.migrate_file(str(target))
    migrate.migrate_file(str(target))
    assert target.read_text(encoding="utf-8").count(migrate.IMPORT_LINE) == 1
