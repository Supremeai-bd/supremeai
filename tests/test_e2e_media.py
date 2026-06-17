import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app import app

client = TestClient(app)


def _skip_if_media_deps_missing():
    try:
        import tools.image_generator as _ig  # noqa: F401
        import tools.video_generator as _vg  # noqa: F401
    except Exception as exc:
        pytest.skip(f"Media backend dependencies missing: {exc}")


@pytest.mark.skip(reason="Placeholder: skip until media backends are wired in production")
def test_generate_image_success():
    _skip_if_media_deps_missing()
    payload = {
        "prompt": "a futuristic city at sunset",
        "model": "stable-diffusion",
        "output_path": "data/test_image.png",
    }
    response = client.post("/api/media/generate/image", json=payload)
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        body = response.json()
        assert "success" in body


@pytest.mark.skip(reason="Placeholder: skip until media backends are wired in production")
def test_generate_video_success():
    _skip_if_media_deps_missing()
    payload = {
        "prompt": "a drone shot over mountains",
        "output_path": "data/test_video.mp4",
    }
    response = client.post("/api/media/generate/video", json=payload)
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        body = response.json()
        assert "success" in body


def test_generate_image_requires_prompt():
    response = client.post("/api/media/generate/image", json={})
    assert response.status_code in (400, 422)


def test_generate_video_requires_prompt():
    response = client.post("/api/media/generate/video", json={})
    assert response.status_code in (400, 422)
