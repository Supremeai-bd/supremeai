import json
import os

os.environ["ENCRYPTION_KEY"] = "9llmzMU2XSRhbAS-R__JMW1XLZzc0ll7obD_RqaVwno="

from byoc.cloud_connector import CloudStatus, list_resources, ping


class TestCloudConnector:
    def test_ping(self):
        import asyncio

        result = asyncio.run(ping())
        assert isinstance(result, CloudStatus)
        assert result.provider == "gcp"
        assert result.connected is False

    def test_list_resources(self):
        import asyncio

        result = asyncio.run(list_resources())
        assert isinstance(result, list)
        assert len(result) == 0

    def test_credential_encryption_and_decryption(self):
        from byoc.cloud_connector import GCPCredentialManager

        sa_data = {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key_id": "abcd123",
            "private_key": "***REMOVED***",
            "client_email": "test-sa@test-project-123.iam.gserviceaccount.com",
        }

        encrypted = GCPCredentialManager.encrypt_credentials(sa_data)
        assert isinstance(encrypted, bytes)
        assert encrypted != json.dumps(sa_data).encode()

        decrypted = GCPCredentialManager.decrypt_credentials(encrypted)
        assert decrypted["project_id"] == "test-project-123"
        assert decrypted["private_key_id"] == "abcd123"

    def test_credential_validation_returns_false_for_malformed(self):
        from byoc.cloud_connector import GCPCredentialManager

        sa_data = {"invalid": "data"}
        is_valid = GCPCredentialManager.validate_service_account(sa_data)
        assert is_valid is False
