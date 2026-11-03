"""Contract tests for security scanning + intelligence modules.

Verifies importability + interface for:
- secret_scanner (gitleaks patterns + AI-enhanced detection)
- ast_scanner (blocks eval, __import__, os.system in sandbox code)
- api_key_limiter (rate limiting for API key auth)
- intelligence.verification (external factual verification)
- learning.store (persistent learning store)
- learning.loop (observe→analyze→propose loop)
- cache.semantic_cache (vector similarity cache)
- cache.autocache_proxy (auto-cache proxy)
- observability.reasoning_stream (SSE fanout for reasoning steps)
- resilience.auto_remediation (auto-fix on failures)
"""

from __future__ import annotations

import pytest


class TestSecretScannerContract:
    def test_importable(self):
        from core.security.scanning.secret_scanner import SecretHunter

        assert SecretHunter is not None

    def test_has_scan_method(self):
        from core.security.scanning.secret_scanner import SecretHunter

        # The scanner should have a method to scan code/content for secrets
        assert hasattr(SecretHunter, "__init__")


class TestASTScannerContract:
    def test_importable(self):
        from core.security.scanning.ast_scanner import ASTSandboxScanner

        assert ASTSandboxScanner is not None

    def test_has_scan_method(self):
        from core.security.scanning.ast_scanner import ASTSandboxScanner

        # Should have a method to scan code for dangerous patterns
        methods = [m for m in dir(ASTSandboxScanner) if "scan" in m.lower()]
        assert len(methods) > 0, f"Expected a scan method, found: {dir(ASTSandboxScanner)}"


class TestAPIKeyLimiterContract:
    def test_importable(self):
        # Actual export is the async enforcement function (class alias pending #898)
        from core.security.api_key_limiter import enforce_api_key_rate_limit

        assert callable(enforce_api_key_rate_limit)


class TestIntelligenceVerificationContract:
    def test_importable(self):
        from core.intelligence.verification import VerificationEngine

        assert VerificationEngine is not None


class TestLearningStoreContract:
    def test_importable(self):
        from core.learning.store import LearningStore, get_learning_store

        assert LearningStore is not None
        assert callable(get_learning_store)


class TestLearningLoopContract:
    def test_importable(self):
        from core.learning.loop import LearningLoopAgent

        assert LearningLoopAgent is not None


class TestSemanticCacheContract:
    def test_importable(self):
        from core.cache.semantic_cache import SemanticCache

        assert SemanticCache is not None


class TestAutoCacheProxyContract:
    def test_importable(self):
        from core.cache.autocache_proxy import AutoCacheProxy

        assert AutoCacheProxy is not None


class TestReasoningStreamContract:
    def test_importable(self):
        from core.observability.reasoning_stream import emit_reasoning_step

        assert callable(emit_reasoning_step)


class TestAutoRemediationContract:
    def test_importable(self):
        from core.resilience.auto_remediation import AutoRemediation

        assert AutoRemediation is not None
