"""`migrate_svc_id.migrate` rewrites env-var reads to the renamed service id.

These migrations touch production code paths, so the rewrite must be:
  * complete — every plain read shape is covered (get / getenv, with and
    without an empty-string default), and
  * additive — the OLD key stays as a fallback, so a deploy that lands before
    the new env var exists still reads the old value instead of crashing.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import migrate_svc_id as migrate  # noqa: E402


def _one_pair():
    assert migrate.MAPPING, "MAPPING must not be empty"
    return next(iter(migrate.MAPPING.items()))


def test_all_read_shapes_are_rewritten():
    old, new = _one_pair()
    source = (
        f'os.environ.get("{old}")\n'
        f'os.environ.get("{old}", "")\n'
        f'os.getenv("{old}")\n'
        f'os.getenv("{old}", "")\n'
    )
    out = migrate.migrate(source)
    assert out.count(new) == 4
    assert f'os.environ.get("{new}", os.environ.get("{old}", ""))' in out


def test_old_key_survives_as_fallback():
    old, new = _one_pair()
    out = migrate.migrate(f'os.environ.get("{old}")')
    assert old in out, "the old env var must remain readable during rollout"
    assert out.index(new) < out.index(old)


def test_unrelated_text_is_untouched():
    source = 'os.environ.get("SOMETHING_ELSE")\nplain text\n'
    assert migrate.migrate(source) == source


def test_migration_is_idempotent():
    old, _new = _one_pair()
    once = migrate.migrate(f'os.environ.get("{old}")')
    assert migrate.migrate(once) == once
