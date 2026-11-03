"""Error remediation tests for SupremeAI 2.0."""

from unittest.mock import MagicMock, patch

import pytest

from core.errors.error_remediation import ErrorRemediation

pytestmark = pytest.mark.anyio


def _skip_if_no_qdrant():
    """Skip test if qdrant_client is not installed."""
    pytest.importorskip("qdrant_client")


class TestErrorRemediation:
    """Tests for ErrorRemediation class."""

    # FIX(#1097): un-skipped — core/errors/error_remediation.py:137-138 still
    # defines _qdrant/_qdrant_initialized; the "attribute removed" reason was stale.
    def test_init_no_qdrant(self):
        """Qdrant ইনস্টল না থাকলেও initialization করা হয় (lazy client)।"""
        # The class lives in core.errors.error_remediation (shim re-exports);
        # patch the REAL module globals and the current _qdrant attribute.
        with patch("core.errors.error_remediation.HAS_QDRANT", False):
            remediation = ErrorRemediation()
            assert remediation._qdrant is None
            assert remediation._qdrant_initialized is False

    # FIX(#1097): un-skipped — same stale-reason audit; lazy-init contract asserted.
    def test_init_with_qdrant(self):
        """Qdrant client এখন lazy — প্রথম lookup-এ তৈরি হয়, __init__-এ নয়।"""
        _skip_if_no_qdrant()
        with patch(
            "core.errors.error_remediation.QdrantClient", return_value=MagicMock()
        ) as mock_client:
            remediation = ErrorRemediation()
            mock_client.assert_not_called()
            assert remediation._qdrant is None

    async def test_lookup_fix_no_qdrant(self):
        """Qdrant ছাড়াই লুকআপ ফিক্স ফলব্যাক রিটার্ন করে।"""
        with patch("core.errors.error_remediation.HAS_QDRANT", False):
            remediation = ErrorRemediation()
            result = await remediation.lookup_fix("error-signature-123")
            assert result is not None and "Retry" in result

    async def test_lookup_fix_success(self):
        """সফলভাবে ফিক্স লুকআপ করা হচ্ছে।"""
        _skip_if_no_qdrant()
        mock_qdrant = MagicMock()
        mock_result = MagicMock()
        mock_result.payload = {"fix": "Retry with exponential backoff"}
        mock_qdrant.search.return_value = [mock_result]

        with patch("core.errors.error_remediation.HAS_QDRANT", True):
            with patch("core.errors.error_remediation.QdrantClient", return_value=mock_qdrant):
                remediation = ErrorRemediation()
                result = await remediation.lookup_fix("error-signature-123")
                assert result == "Retry with exponential backoff"

    async def test_lookup_fix_no_results(self):
        """ফিক্স পাওয়া না গেলে None রিটার্ন করে।"""
        _skip_if_no_qdrant()
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        with patch("core.errors.error_remediation.HAS_QDRANT", True):
            with patch("core.errors.error_remediation.QdrantClient", return_value=mock_qdrant):
                remediation = ErrorRemediation()
                result = await remediation.lookup_fix("error-signature-123")
                assert result is not None and "Retry" in result

    async def test_lookup_fix_exception(self):
        """ত্রুটি হলে None রিটার্ন করে।"""
        _skip_if_no_qdrant()
        mock_qdrant = MagicMock()
        mock_qdrant.search.side_effect = Exception("Qdrant connection error")

        with patch("core.errors.error_remediation.HAS_QDRANT", True):
            with patch("core.errors.error_remediation.QdrantClient", return_value=mock_qdrant):
                remediation = ErrorRemediation()
                result = await remediation.lookup_fix("error-signature-123")
                assert result is not None and "Retry" in result
