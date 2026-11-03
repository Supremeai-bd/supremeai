import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app import app

client = TestClient(app)


def _skip_if_media_deps_missing():
    try:
        import tools.media.image_generator as _ig  # noqa: F401 -- শুধু availability probe
        import tools.media.video_generator as _vg  # noqa: F401 -- শুধু availability probe
    except Exception as exc:
        pytest.skip(f"Media backend dependencies missing: {exc}")


def test_generate_upload_url_requires_fields():
    response = client.post("/api/v1/media/generate-upload-url", json={})
    assert response.status_code == 422


def test_generate_upload_url_success():
    from unittest.mock import patch

    with patch(
        "storage.r2_storage_client.R2StorageClient.generate_presigned_upload_url",
        return_value="https://mock-upload-url.com",
    ):
        payload = {
            "file_name": "test.png",
            "file_type": "image/png",
            "folder": "test_folder",
        }
        response = client.post("/api/v1/media/generate-upload-url", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "upload_url" in body
        assert "file_path" in body
        assert "public_url" in body
