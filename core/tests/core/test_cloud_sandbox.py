import base64
import hashlib
import hmac
import os
import struct
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.orchestration.cloud_sandbox_orchestrator import CloudSandboxOrchestrator


class TestCloudSandboxOrchestrator:
    """Tests for CloudSandboxOrchestrator class."""

    def test_init_runpod_provider(self):
        """RunPod provider initialization test করা হচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        assert orchestrator.provider == "runpod"
        assert "api.runpod.io" in orchestrator.base_url

    def test_init_modal_provider(self):
        """Modal provider initialization test করা হচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="modal")
        assert orchestrator.provider == "modal"
        assert "api.modal.com" in orchestrator.base_url

    def test_init_invalid_provider(self):
        """Invalid provider raises ValueError test করা হচ্ছে।"""
        with pytest.raises(ValueError, match="Unsupported provider"):
            CloudSandboxOrchestrator(provider="invalid")

    @pytest.mark.anyio
    async def test_create_sandbox_no_api_key_mock_mode(self):
        """API কী ছাড়াই মক মোডে স্যান্ডবক্স তৈরি হচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        assert orchestrator.api_key is None

        result = await orchestrator.create_sandbox(spec={"imageName": "ubuntu"})
        assert result is not None
        assert result["id"].startswith("mock-sandbox-id-")
        assert result["status"] == "running"
        assert result["mock"] is True

    @pytest.mark.anyio
    async def test_get_sandbox_status_no_api_key_mock_mode(self):
        """API কী ছাড়াই স্যান্ডবক্স স্ট্যাটাস পেতে মক রেসপন্স পাওয়া যাচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        result = await orchestrator.get_sandbox_status("test-sandbox-id")
        assert result is not None
        assert result["id"] == "test-sandbox-id"
        assert result["status"] == "running"
        assert result["mock"] is True

    @pytest.mark.anyio
    async def test_run_command_no_api_key_mock_mode(self):
        """API কী ছাড়াই কমান্ড চালানোর মক রেসপন্স পাওয়া যাচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        result = await orchestrator.run_command("test-sandbox-id", "ls -la")
        assert result is not None
        # audit B-07 fix: mock mode must NOT fake a successful execution.
        assert result["status"] == "MOCK_NOT_EXECUTED"
        assert result["exitCode"] is None
        assert result["stdout"] == ""
        assert "NOT" in result["stderr"]
        assert result["mock"] is True

    @pytest.mark.anyio
    async def test_destroy_sandbox_no_api_key_mock_mode(self):
        """স্যান্ডবক্স ধ্বংস করা সফল হচ্ছে (মক মোড)।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        result = await orchestrator.destroy_sandbox("test-sandbox-id")
        assert result is True

    @pytest.mark.anyio
    async def test_create_sandbox_with_api_key_runpod(self):
        """RunPod API কী সহ স্যান্ডবক্স তৈরি করা হচ্ছে।"""
        with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-api-key"}, clear=False):
            orchestrator = CloudSandboxOrchestrator(provider="runpod")

            with patch.object(orchestrator, "_get_endpoint", return_value="/"):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "id": "pod-12345",
                    "status": "created",
                }
                mock_response.raise_for_status = MagicMock()

                with (
                    patch.object(
                        orchestrator.client,
                        "post",
                        new_callable=AsyncMock,
                        return_value=mock_response,
                    ),
                    patch.object(
                        orchestrator,
                        "_prepare_creation_payload",
                        return_value={"pod": {"imageName": "ubuntu"}},
                    ),
                ):
                    result = await orchestrator.create_sandbox(spec={"imageName": "ubuntu"})
                    assert result is not None
                    assert result["id"] == "pod-12345"

    @pytest.mark.anyio
    async def test_run_command_with_api_key(self):
        """API কী সহ কমান্ড চালানো হচ্ছে।"""
        with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-api-key"}, clear=False):
            orchestrator = CloudSandboxOrchestrator(provider="runpod")

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "COMPLETED",
                "exitCode": 0,
                "stdout": "output",
            }
            mock_response.raise_for_status = MagicMock()

            with (
                patch.object(
                    orchestrator.client,
                    "post",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ),
                patch.object(orchestrator, "_get_endpoint", return_value="/pod-12345/run"),
            ):
                result = await orchestrator.run_command("pod-12345", "echo hello")
                assert result is not None
                assert result["exitCode"] == 0

    @pytest.mark.anyio
    async def test_run_command_api_error(self):
        """API ত্রুটি হলে স্যান্ডবক্স চালানো ব্যর্থ হয়।"""
        with patch.dict(os.environ, {"RUNPOD_API_KEY": "test-api-key"}, clear=False):
            orchestrator = CloudSandboxOrchestrator(provider="runpod")

            import httpx

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=mock_response
            )

            with (
                patch.object(
                    orchestrator.client,
                    "post",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ),
                patch.object(orchestrator, "_get_endpoint", return_value="/pod-12345/run"),
            ):
                result = await orchestrator.run_command("pod-12345", "echo hello")
                assert result is None

    def test_get_endpoint_create(self):
        """এন্ডপয়েন্ট পাবলিশ করা হচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        endpoint = orchestrator._get_endpoint("create")
        assert endpoint == "/"

    def test_get_endpoint_status(self):
        """স্ট্যাটাস এন্ডপয়েন্ট পাওয়া যাচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        endpoint = orchestrator._get_endpoint("status", "pod-123")
        assert endpoint == "/pod-123"

    def test_get_endpoint_run(self):
        """রান এন্ডপয়েন্ট পাওয়া যাচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        endpoint = orchestrator._get_endpoint("run", "pod-123")
        assert endpoint == "/pod-123/run"

    def test_get_endpoint_destroy(self):
        """ডেস্ট্রয় এন্ডপয়েন্ট পাওয়া যাচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        endpoint = orchestrator._get_endpoint("destroy", "pod-123")
        assert endpoint == "/pod-123/terminate"

    def test_prepare_creation_payload_runpod(self):
        """RunPod পেলোড প্রস্তুত করা হচ্ছে।"""
        orchestrator = CloudSandboxOrchestrator(provider="runpod")
        payload = orchestrator._prepare_creation_payload({"imageName": "ubuntu"})
        assert payload == {"pod": {"imageName": "ubuntu"}}

    def test_prepare_creation_payload_modal_raises(self):
        """Modal পেলোড প্রস্তুত করা হলে NotImplementedError হয়।"""
        orchestrator = CloudSandboxOrchestrator(provider="modal")
        with pytest.raises(NotImplementedError):
            orchestrator._prepare_creation_payload({"imageName": "ubuntu"})


class TestTOTPVerification:
    """TOTP verification functions tests."""

    def test_verify_totp_code_success(self):
        """সঠিক TOTP কোড ভেরিফাই করা হয়।"""
        from api.routes.admin_routes import verify_totp_code

        # Generate a valid TOTP code for testing
        secret = base64.b32encode(os.urandom(10)).decode("utf-8")
        current_time = int(time.time() // 30)
        missing_padding = len(secret) % 8
        if missing_padding:
            secret += "=" * (8 - missing_padding)
        key = base64.b32decode(secret.upper())
        msg = struct.pack(">Q", current_time)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[19] & 15
        h_num = struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF
        valid_code = f"{h_num % 1000000:06d}"

        assert verify_totp_code(valid_code, secret) is True

        """TOTP কোড প্রসੂসিং এ এক্সেপশন হলে False রিটার্ন করে।"""
        from api.routes.admin_routes import verify_totp_code

        assert verify_totp_code("123456", "") is False
        assert verify_totp_code("123456", "invalid-secret!!!") is False

    def test_check_totp_success(self):
        """check_totp ফাংশন সফল ভেরিফিকেশন রিটার্ন করে।"""
        from api.routes.admin_routes import check_totp

        secret = base64.b32encode(os.urandom(10)).decode("utf-8")
        current_time = int(time.time() // 30)
        missing_padding = len(secret) % 8
        if missing_padding:
            secret += "=" * (8 - missing_padding)
        key = base64.b32decode(secret.upper())
        msg = struct.pack(">Q", current_time)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        o = h[19] & 15
        h_num = struct.unpack(">I", h[o : o + 4])[0] & 0x7FFFFFFF
        valid_code = f"{h_num % 1000000:06d}"

        assert check_totp(valid_code, secret) is True
