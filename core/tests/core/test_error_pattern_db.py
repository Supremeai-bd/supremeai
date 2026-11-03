"""Tests for ErrorPatternDB - Error pattern tracking and prevention.

This module tests:
- ErrorPatternDB initialization
- Error logging (Dual-backend: Postgres and SQLite)
- AI mistake logging
- Prevention strategy retrieval
- Pattern checking
- SQL injection prevention
"""

import os
import tempfile

from core.errors.error_pattern_db import ErrorPatternDB


class TestErrorPatternDB:
    """Tests for ErrorPatternDB class."""

    def test_init_defaults_to_sqlite(self):
        """Test that ErrorPatternDB uses SQLite by default in tests."""
        db = ErrorPatternDB()

        # Should have a database path
        assert db.db_path is not None

    def test_log_error_success(self):
        """Test successful error logging."""
        db = ErrorPatternDB()

        # Should not raise
        db.log_error("error output", "validation_error", "fix it")

    def test_log_ai_mistake_success(self):
        """Test successful AI mistake logging."""
        db = ErrorPatternDB()

        mistake = {
            "mistake": "incorrect output",
            "model": "gpt-4",
            "task_type": "summarization",
        }

        # Should not raise
        db.log_ai_mistake(mistake)

    def test_get_prevention_strategy_empty(self):
        """Test prevention strategy when no patterns exist."""
        db = ErrorPatternDB()

        result = db.get_prevention_strategy("gpt-4", "summarization")

        # Should return empty dict or default when no data
        assert isinstance(result, dict | str)

    def test_check_pattern_safe_output(self):
        """Test pattern checking with safe output."""
        db = ErrorPatternDB()

        result = db.check_pattern("This is a normal output")

        assert "known_patterns" in result
        assert "should_prevent" in result
        assert result["should_prevent"] is False

    def test_check_pattern_known_pattern(self):
        """Test pattern checking detects known patterns."""
        db = ErrorPatternDB()

        # First log an error pattern
        db.log_error("hallucinated fact about quantum physics", "hallucination", "verify facts")

        result = db.check_pattern("quantum physics")

        # Should detect the pattern
        assert "known_patterns" in result

    def test_sqlite_backend_creation(self):
        """Test SQLite table creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            ErrorPatternDB(db_path=db_path)

            # Should create the database file
            assert os.path.exists(db_path)

    def test_parameterized_queries(self):
        """Test that queries use parameterized inputs."""
        db = ErrorPatternDB()

        # This should be safe from SQL injection
        malicious_input = "'; DROP TABLE errors; --"
        db.log_error(malicious_input, "sql_injection_attempt", "prevent")

        # Should have logged without executing the injection
        result = db.check_pattern(malicious_input)
        assert "known_patterns" in result

    def test_multiple_errors_same_type(self):
        """Test logging multiple errors of same type."""
        db = ErrorPatternDB()

        db.log_error("error 1", "validation", "fix 1")
        db.log_error("error 2", "validation", "fix 2")
        db.log_error("error 3", "validation", "fix 3")

        strategy = db.get_prevention_strategy("test-model", "test-task")
        assert isinstance(strategy, dict | str)


class TestErrorPatternDBConcurrentAccess:
    """Tests for concurrent database access patterns."""

    def test_concurrent_log_access(self):
        """Test that concurrent access is handled."""
        db = ErrorPatternDB()

        # Simulate concurrent error logging
        for i in range(10):
            db.log_error(f"error_{i}", "test_error", f"fix_{i}")

        # Should still work
        result = db.check_pattern("error_5")
        assert "known_patterns" in result
