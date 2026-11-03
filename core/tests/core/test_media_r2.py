from unittest.mock import MagicMock, patch

import pytest

from storage.r2_storage_client import R2StorageClient, StorageNotConfiguredError

# বাংলা মন্তব্য: ক্লাউডফ্লেয়ার R2 এর প্রে-সাইনড ইউআরএল জেনারেট করার লজিক টেস্ট করা হচ্ছে।


def test_r2_client_unconfigured_fails_closed():
    # বাংলা মন্তব্য: ক্রেডেনশিয়াল না থাকলে আর ভুয়া mock URL নেই — সৎ StorageNotConfiguredError
    # (audit B-01 fix)। আগে https://mock-r2-upload.local/... ফেরত দিয়ে আপলোড "সফল" সাজানো হতো।
    with patch.dict("os.environ", {}, clear=True):
        client = R2StorageClient()
        assert client.dry_run is True

        with pytest.raises(StorageNotConfiguredError):
            client.generate_presigned_upload_url("test_file.txt", "text/plain")

        with pytest.raises(StorageNotConfiguredError):
            client.generate_presigned_download_url("test_file.txt")


def test_r2_client_generate_presigned_url():
    # বাংলা মন্তব্য: ক্রেডেনশিয়াল থাকলে boto3 সাকসেসফুলি প্রে-সাইনড ইউআরএল তৈরি করছে কিনা তা যাচাইয়ের টেস্ট।
    env_vars = {
        "R2_ACCOUNT_ID": "mock_account_id",
        "R2_ACCESS_KEY": "mock_access_key",
        "R2_SECRET_KEY": "mock_secret_key",
        "R2_BUCKET_NAME": "mock-bucket",
    }

    with patch.dict("os.environ", env_vars):
        with patch("boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = (
                "https://r2-real-url.com/mock-bucket/test_file.txt"
            )
            mock_boto.return_value = mock_s3

            client = R2StorageClient()
            assert client.dry_run is False

            url = client.generate_presigned_upload_url("test_file.txt", "text/plain")
            assert url == "https://r2-real-url.com/mock-bucket/test_file.txt"
            mock_s3.generate_presigned_url.assert_called_once()


def test_media_route_generate_upload_url():
    # বাংলা মন্তব্য: FastAPI টেস্ট ক্লায়েন্ট ব্যবহার করে সরাসরি এপিআই এন্ডপয়েন্ট টেস্ট করা হচ্ছে।
    from fastapi.testclient import TestClient

    from core.app import app

    test_client = TestClient(app)
    payload = {
        "file_name": "skills_bundle.zip",
        "file_type": "application/zip",
        "folder": "test_folder",
    }
    headers = {"Authorization": "Bearer test_token"}

    # বাংলা মন্তব্য: R2 কনফিগার না থাকলে সৎ 503 — কোনো ভুয়া upload URL নেই (audit B-01)।
    response = test_client.post(
        "/api/v1/media/generate-upload-url",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]

    # বাংলা মন্তব্য: স্টোরেজ available হলে (mock-patched) রুট সফলভাবে URL দেয়।
    with patch(
        "api.routes.media.storage_client.generate_presigned_upload_url",
        return_value="https://r2-real-url.com/test/skills_bundle.zip",
    ):
        response = test_client.post(
            "/api/v1/media/generate-upload-url",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "file_path" in data
        assert "skills_bundle.zip" in data["file_path"]
