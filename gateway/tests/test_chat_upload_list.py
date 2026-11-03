"""ERR-B02 tests — /api/chat/upload LIST endpoint (files explorer backend).

বাংলা: /files পেজ আগে blank ছিল (ERR-B02) — chat_upload-এ লিস্ট এন্ডপয়েন্টই
ছিল না, তাই ফাইল এক্সপ্লোরার বানানো অসম্ভব ছিল। এই টেস্টগুলো নতুন LIST
এন্ডপয়েন্ট + sidecar metadata persistence pin করে রাখে।
"""

import io

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio]


def _png_bytes(size: int = 64) -> bytes:
    """Minimal payload that passes the PNG header validation."""
    header = b"\x89PNG\r\n\x1a\n"
    return header + b"\x00" * size


@pytest.fixture
def upload_files():
    return {"file": ("team-photo.png", io.BytesIO(_png_bytes()), "image/png")}


class TestUploadList:
    async def test_list_empty_initially(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/chat/upload", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total"}

    async def test_upload_then_list_shows_file(
        self, client: AsyncClient, auth_headers, upload_files, tmp_path
    ):
        up = await client.post("/api/chat/upload/", headers=auth_headers, files=upload_files)
        assert up.status_code == 200, up.text
        created = up.json()
        assert created["name"] == "team-photo.png"

        listing = await client.get("/api/chat/upload", headers=auth_headers)
        assert listing.status_code == 200
        items = listing.json()["items"]
        match = [i for i in items if i["attachment_id"] == created["attachment_id"]]
        assert len(match) == 1
        assert match[0]["name"] == "team-photo.png"
        assert match[0]["mime_type"] == "image/png"
        assert match[0]["size"] > 0
        assert match[0]["created_at"]

    async def test_sidecar_survives_registry_loss(
        self, client: AsyncClient, auth_headers, upload_files
    ):
        """After a restart the in-memory registry is empty — the sidecar + disk
        scan must still produce a correct listing (name preserved)."""
        up = await client.post("/api/chat/upload/", headers=auth_headers, files=upload_files)
        created = up.json()

        from api.routes.chat_upload import _uploads

        _uploads.pop(created["attachment_id"], None)  # simulate restart

        listing = await client.get("/api/chat/upload", headers=auth_headers)
        items = listing.json()["items"]
        match = [i for i in items if i["attachment_id"] == created["attachment_id"]]
        assert len(match) == 1, "file must still be listed from disk after registry loss"
        assert match[0]["name"] == "team-photo.png"

    async def test_delete_removes_from_listing(
        self, client: AsyncClient, auth_headers, upload_files
    ):
        up = await client.post("/api/chat/upload/", headers=auth_headers, files=upload_files)
        created = up.json()

        gone = await client.delete(
            f"/api/chat/upload/{created['attachment_id']}", headers=auth_headers
        )
        assert gone.status_code == 200

        listing = await client.get("/api/chat/upload", headers=auth_headers)
        items = listing.json()["items"]
        assert all(i["attachment_id"] != created["attachment_id"] for i in items)

    async def test_rejects_non_image(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/chat/upload/",
            headers=auth_headers,
            files={"file": ("payload.bin", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        )
        assert resp.status_code == 415
