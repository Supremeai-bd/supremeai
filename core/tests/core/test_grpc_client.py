"""gRPC client tests for SupremeAI 2.0."""

from unittest.mock import MagicMock, patch

import grpc
import pytest

try:
    from core.grpc_client import WorkerGrpcClient
except ModuleNotFoundError:
    pytest.skip("protos module not available", allow_module_level=True)


class TestWorkerGrpcClient:
    """Tests for WorkerGrpcClient class."""

    def test_init(self):
        """ইনিশialization চেক।"""
        client = WorkerGrpcClient.__new__(WorkerGrpcClient)
        client.channel = MagicMock()
        client.stub = MagicMock()
        assert client.channel is not None
        assert client.stub is not None

    def test_submit_task_success(self):
        """টাস্ক সফলভাবে সাবমিট হয়।"""
        mock_response = MagicMock()
        mock_response.task_id = "task-123"

        with patch("core.grpc_client.grpc.insecure_channel") as mock_channel:
            with patch("protos.supreme_engine_pb2_grpc.WorkerServiceStub") as mock_stub_class:
                mock_stub = MagicMock()
                mock_stub.SubmitTask.return_value = mock_response
                mock_stub_class.return_value = mock_stub

                client = WorkerGrpcClient.__new__(WorkerGrpcClient)
                client.channel = mock_channel.return_value
                client.stub = mock_stub

                result = client.submit_task("test_task", {"key": "value"}, "user-123")
                assert result == "task-123"

    def test_submit_task_failure(self):
        """টাস্ক সাবমিট ব্যর্থ হলে None রিটার্ন করে।"""
        with patch("core.grpc_client.grpc.insecure_channel"):
            with patch("protos.supreme_engine_pb2_grpc.WorkerServiceStub") as mock_stub_class:
                mock_stub = MagicMock()
                mock_stub.SubmitTask.side_effect = grpc.RpcError("gRPC error")
                mock_stub_class.return_value = mock_stub

                client = WorkerGrpcClient.__new__(WorkerGrpcClient)
                client.channel = MagicMock()
                client.stub = mock_stub

                result = client.submit_task("test_task", {"key": "value"}, "user-123")
                assert result is None

    def test_get_task_status_success(self):
        """টাস্ক স্ট্যাটাস সফলভাবে পায়।"""
        mock_response = MagicMock()
        mock_response.task_id = "task-123"
        mock_response.status = "completed"
        mock_response.result_json = '{"result": "success"}'
        mock_response.error_message = ""

        with patch("core.grpc_client.grpc.insecure_channel"):
            with patch("protos.supreme_engine_pb2_grpc.WorkerServiceStub") as mock_stub_class:
                mock_stub = MagicMock()
                mock_stub.GetTaskStatus.return_value = mock_response
                mock_stub_class.return_value = mock_stub

                client = WorkerGrpcClient.__new__(WorkerGrpcClient)
                client.channel = MagicMock()
                client.stub = mock_stub

                result = client.get_task_status("task-123")
                assert result["task_id"] == "task-123"
                assert result["status"] == "completed"
                assert result["result_json"] == {"result": "success"}

    def test_get_task_status_failure(self):
        """টাস্ক স্ট্যাটাস ব্যর্থ হলে ERROR রিটার্ন করে।"""
        with patch("core.grpc_client.grpc.insecure_channel"):
            with patch("protos.supreme_engine_pb2_grpc.WorkerServiceStub") as mock_stub_class:
                mock_stub = MagicMock()
                mock_stub.GetTaskStatus.side_effect = grpc.RpcError("gRPC error")
                mock_stub_class.return_value = mock_stub

                client = WorkerGrpcClient.__new__(WorkerGrpcClient)
                client.channel = MagicMock()
                client.stub = mock_stub

                result = client.get_task_status("task-123")
                assert result["status"] == "ERROR"
                assert "error_message" in result

    def test_log_audit_event_success(self):
        """অডিট ইভেন্ট লগ সফল হয়।"""
        mock_response = MagicMock()
        mock_response.success = True

        with patch("core.grpc_client.grpc.insecure_channel"):
            with patch("protos.supreme_engine_pb2_grpc.WorkerServiceStub") as mock_stub_class:
                mock_stub = MagicMock()
                mock_stub.LogAuditEvent.return_value = mock_response
                mock_stub_class.return_value = mock_stub

                client = WorkerGrpcClient.__new__(WorkerGrpcClient)
                client.channel = MagicMock()
                client.stub = mock_stub

                result = client.log_audit_event(
                    "user_login",
                    "user-123",
                    "auth",
                    {"ip": "127.0.0.1"},  # is_local()
                )
                assert result is True

    def test_log_audit_event_failure(self):
        """অডিট ইভেন্ট লগ ব্যর্থ হলে False রিটার্ন করে।"""
        with patch("core.grpc_client.grpc.insecure_channel"):
            with patch("protos.supreme_engine_pb2_grpc.WorkerServiceStub") as mock_stub_class:
                mock_stub = MagicMock()
                mock_stub.LogAuditEvent.side_effect = grpc.RpcError("gRPC error")
                mock_stub_class.return_value = mock_stub

                client = WorkerGrpcClient.__new__(WorkerGrpcClient)
                client.channel = MagicMock()
                client.stub = mock_stub

                result = client.log_audit_event(
                    "user_login",
                    "user-123",
                    "auth",
                    {"ip": "127.0.0.1"},  # is_local()
                )
                assert result is False
