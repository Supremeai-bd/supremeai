"""
Tests for services/minio_client.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.minio_client import MinIOClient, StoredObject


def test_stored_object_dataclass():
    obj = StoredObject(
        bucket="b",
        key="k",
        size=1024,
        etag="abc",
        content_type="text/plain",
        url="http://s/b/k",
        stored_at="2024-01-01T00:00:00Z",
    )
    assert obj.bucket == "b"
    assert obj.size == 1024


@pytest.mark.anyio
async def test_upload_calls_minio_fput_object():
    client = MinIOClient()
    mock_minio = MagicMock()
    mock_minio.fput_object.return_value = MagicMock(etag="etag123", size=123)

    client._client = mock_minio
    result = await client.upload(
        bucket="uploads",
        key="file.txt",
        file_path="C:/tmp/file.txt",
        content_type="text/plain",
    )

    assert result["status"] == "success"
    mock_minio.fput_object.assert_called_once()


@pytest.mark.anyio
async def test_download_writes_file(tmp_path):
    client = MinIOClient()
    mock_minio = MagicMock()
    mock_minio.fget_object = AsyncMock()

    client._client = mock_minio
    dest = str(tmp_path / "out.txt")
    ok = await client.download("bucket", "key", dest)

    assert ok is True
    mock_minio.fget_object.assert_called_once()


@pytest.mark.anyio
async def test_get_presigned_url_returns_url():
    client = MinIOClient()
    mock_minio = MagicMock()
    mock_minio.presigned_get_object.return_value = (
        "http://localhost:9000/bucket/key?sign=xyz"  # is_local()
    )

    client._client = mock_minio
    url = await client.get_presigned_url("bucket", "key", expires_seconds=3600)

    assert url.startswith("http")
    mock_minio.presigned_get_object.assert_called_once()


@pytest.mark.anyio
async def test_list_objects_returns_stored_objects():
    client = MinIOClient()
    mock_obj = MagicMock()
    mock_obj.object_name = "dir/a.txt"
    mock_obj.size = 10
    mock_obj.etag = "etag1"
    mock_obj.content_type = "text/plain"

    mock_minio = MagicMock()
    mock_minio.list_objects.return_value = [mock_obj]

    client._client = mock_minio
    objs = await client.list_objects("bucket", prefix="dir/")

    assert len(objs) == 1
    assert objs[0].key == "dir/a.txt"
    assert objs[0].etag == "etag1"
