# tests/test_core_error_handling.py
"""Tests for error handling and remediation systems."""

import pytest


class TestErrorPatternDB:
    """Test error pattern database functionality."""

    def test_error_pattern_db_initialization(self):
        """Test ErrorPatternDB initializes with default path."""
        from core.errors.error_pattern_db import ErrorPatternDB

        db = ErrorPatternDB()
        assert db is not None

    def test_error_pattern_db_custom_path(self):
        """Test ErrorPatternDB with custom path."""
        from core.errors.error_pattern_db import ErrorPatternDB

        db = ErrorPatternDB(db_path=":memory:")
        assert db is not None

    def test_log_error(self):
        """Test logging an error pattern."""
        from core.errors.error_pattern_db import ErrorPatternDB

        db = ErrorPatternDB(db_path=":memory:")

        # Log an error
        db.log_error(
            output="TypeError: 'NoneType' object is not subscriptable",
            error_type="TypeError",
            correction="Add null check before subscripting",
        )

        # Verify it was logged in either in-memory ring or sqlite table
        if db._use_memory:
            assert len(db._memory_errors) >= 1
            assert db._memory_errors[-1]["error_type"] == "TypeError"
        elif not db._use_pg:
            conn = db._connect()
            row = (
                conn.cursor()
                .execute("SELECT error_type FROM errors WHERE error_type = 'TypeError'")
                .fetchone()
            )
            assert row is not None
            assert row[0] == "TypeError"

    def test_log_ai_mistake(self):
        """Test logging AI mistake."""
        from core.errors.error_pattern_db import ErrorPatternDB

        db = ErrorPatternDB(db_path=":memory:")

        mistake = {
            "type": "ValueError",
            "original": "Invalid input provided",
            "task": "string_parsing",
        }

        db.log_ai_mistake(mistake)
        if db._use_memory:
            assert len(db._memory_mistakes) >= 1
            assert db._memory_mistakes[-1]["mistake_type"] == "ValueError"
        elif not db._use_pg:
            conn = db._connect()
            row = (
                conn.cursor()
                .execute("SELECT mistake_type FROM ai_mistakes WHERE mistake_type = 'ValueError'")
                .fetchone()
            )
            assert row is not None
            assert row[0] == "ValueError"

    def test_get_prevention_strategy(self):
        """Test getting prevention strategy."""
        from core.errors.error_pattern_db import ErrorPatternDB

        db = ErrorPatternDB(db_path=":memory:")

        strategy = db.get_prevention_strategy(model="gemini", task_type="code_generation")

        # Should return a string or None
        assert strategy is None or isinstance(strategy, str)

    def test_check_pattern(self):
        """Test pattern checking."""
        from core.errors.error_pattern_db import ErrorPatternDB

        db = ErrorPatternDB(db_path=":memory:")

        result = db.check_pattern("TypeError: NoneType")

        assert isinstance(result, dict)


class TestErrorRemediation:
    """Test error remediation functionality."""

    def test_error_remediation_initialization(self):
        """Test ErrorRemediation initializes."""
        from core.errors.error_remediation import ErrorRemediation

        remediation = ErrorRemediation()
        assert remediation is not None

    @pytest.mark.asyncio
    async def test_lookup_fix(self):
        """Test looking up error fix."""
        from core.errors.error_remediation import ErrorRemediation

        remediation = ErrorRemediation()

        # Lookup should return a fix or None
        fix = await remediation.lookup_fix("TypeError: NoneType object")

        # Could be None if no matching pattern
        assert fix is None or isinstance(fix, str)

    @pytest.mark.asyncio
    async def test_backoff_retry(self):
        """Test exponential backoff retry mechanism."""
        from core.errors.error_remediation import ErrorRemediation

        remediation = ErrorRemediation()

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await remediation._backoff_retry(failing_operation, max_attempts=3)

        assert result == "success"
        assert call_count == 3


class TestGenerationMonitor:
    """Test generation monitoring functionality."""

    def test_generation_monitor_initialization(self):
        """Test GenerationMonitor initializes."""
        from core.generation_monitor import GenerationMonitor

        monitor = GenerationMonitor()
        assert monitor is not None

    def test_track_token_confidence(self):
        """Test tracking token confidence."""
        from core.generation_monitor import GenerationMonitor

        monitor = GenerationMonitor()

        result = monitor.track_token_confidence(token="def", probability=0.95)

        assert isinstance(result, dict)

    def test_flag_factual_claims(self):
        """Test flagging factual claims in output."""
        from core.generation_monitor import GenerationMonitor

        monitor = GenerationMonitor()

        text = "The capital of France is Paris. The Earth is flat."
        claims = monitor.flag_factual_claims(text)

        assert isinstance(claims, list)

    def test_check_consistency(self):
        """Test consistency checking."""
        from core.generation_monitor import GenerationMonitor

        monitor = GenerationMonitor()

        result = monitor.check_consistency(
            new_text="The answer is 42",
            conversation_history=[{"user": "What is 2+2?", "assistant": "4"}],
        )

        assert isinstance(result, dict)
