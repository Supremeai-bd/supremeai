# বাংলা মন্তব্য: Issue #2505 — performance_metrics টেবিল সুরক্ষা ও নো-ড্রপ রিগ্রেশন গার্ড টেস্ট।
"""Regression tests ensuring superseded migration k5l6m7n8o9p0 does not drop live data."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic_migrations"
    / "versions"
    / "k5l6m7n8o9p0_drop_dead_performance_metrics.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("k5l6_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_k5l6_migration_upgrade_does_not_drop_table():
    """Verify upgrade() in k5l6 is a safe no-op and never calls op.drop_table."""
    migration = _load_migration_module()
    with patch("alembic.op.drop_table") as mock_drop:
        migration.upgrade()
        mock_drop.assert_not_called()


def test_k5l6_migration_downgrade_is_safe_noop():
    """Verify downgrade() in k5l6 is a safe no-op."""
    migration = _load_migration_module()
    with patch("alembic.op.drop_table") as mock_drop:
        migration.downgrade()
        mock_drop.assert_not_called()
