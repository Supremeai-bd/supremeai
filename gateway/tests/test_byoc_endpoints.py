from unittest.mock import patch

from fastapi.testclient import TestClient

from core.app import app

client = TestClient(app)


def test_byoc_credentials_upload_validates_and_encrypts():
    sa_payload = {
        "provider": "gcp",
        "gcp_credentials": {
            "type": "service_account",
            "project_id": "valid-gcp-project",
            "private_key_id": "pkey123",
            "private_key": "***REMOVED***",
            "client_email": "sa@valid-gcp-project.iam.gserviceaccount.com",
        },
    }

    # Mock validate_service_account to pass
    with patch(
        "byoc.cloud_connector.GCPCredentialManager.validate_service_account",
        return_value=True,
    ):
        resp = client.post("/api/byoc/credentials", json=sa_payload)

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_byoc_credentials_upload_fails_on_malformed_fields():
    sa_payload = {
        "provider": "gcp",
        "gcp_credentials": {
            "type": "service_account",
            "project_id": "INVALID_PROJECT_ID_WITH_CAPS",
            "private_key_id": "pkey123",
            "private_key": "somekey",
            "client_email": "invalid-email",
        },
    }
    resp = client.post("/api/byoc/credentials", json=sa_payload)
    # Pydantic validation should block before route execution (status code 422 Unprocessable Entity)
    assert resp.status_code == 422


def test_byoc_deployment_fails_without_credentials():
    from api.routes.byoc_api import active_jobs, encrypted_vault

    encrypted_vault.clear()
    active_jobs.clear()

    # Attempt deployment without credentials uploaded first
    deploy_payload = {"skill_name": "sentiment-analysis", "provider": "gcp"}
    resp = client.post("/api/byoc/deploy", json=deploy_payload)
    assert resp.status_code == 400
    assert "credentials not found" in resp.json()["detail"].lower()


def test_byoc_deployment_triggers_quota_enforcement():
    from api.routes.byoc_api import active_jobs, encrypted_vault

    encrypted_vault.clear()
    active_jobs.clear()

    # 1. Upload valid credentials first to pass check
    sa_payload = {
        "provider": "gcp",
        "gcp_credentials": {
            "type": "service_account",
            "project_id": "valid-gcp-project",
            "private_key_id": "pkey123",
            "private_key": "***REMOVED***",
            "client_email": "sa@valid-gcp-project.iam.gserviceaccount.com",
        },
    }
    with patch(
        "byoc.cloud_connector.GCPCredentialManager.validate_service_account",
        return_value=True,
    ):
        client.post("/api/byoc/credentials", json=sa_payload)

    # 2. Trigger deployment (should succeed/pending 200 OK)
    deploy_payload = {"skill_name": "sentiment-analysis", "provider": "gcp"}
    resp = client.post("/api/byoc/deploy", json=deploy_payload)
    assert resp.status_code == 200
    assert "job_id" in resp.json()
