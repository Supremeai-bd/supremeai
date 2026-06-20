import os
import tempfile
import sqlite3

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest


@pytest.fixture
def audit_logger(tmp_path):
    from core.audit_logger import AuditLogger
    db_path = str(tmp_path / "audit_test.db")
    return AuditLogger(db_path), db_path


class TestAuditLogger:
    def test_log_decision_writes_row(self, audit_logger):
        logger, db_path = audit_logger
        logger.log_decision("action_x", "details here", "because reasons")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM audit_logs").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["action_type"] == "action_x"

    def test_log_decision_multiple_entries(self, audit_logger):
        logger, _ = audit_logger
        logger.log_decision("a", "d1", "r1")
        logger.log_decision("b", "d2", "r2")
        trail = logger.get_audit_trail()
        assert len(trail) == 2

    def test_get_audit_trail_returns_list(self, audit_logger):
        logger, _ = audit_logger
        trail = logger.get_audit_trail()
        assert isinstance(trail, list)

    def test_get_audit_trail_returns_all_entries(self, audit_logger):
        logger, _ = audit_logger
        logger.log_decision("first", "d", "r")
        logger.log_decision("second", "d", "r")
        trail = logger.get_audit_trail()
        action_types = [t["action_type"] for t in trail]
        assert "first" in action_types
        assert "second" in action_types

    def test_log_decision_with_special_characters(self, audit_logger):
        logger, _ = audit_logger
        logger.log_decision("unicode_test", "détails", "réasoning 🚀")
        trail = logger.get_audit_trail()
        assert trail[0]["decision_details"] == "détails"
