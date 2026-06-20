from unittest.mock import MagicMock, patch
from tools.video_generator import VideoGenerator


def _make_generator():
    return VideoGenerator(runway_api_key="runway-key", kling_api_key="kling-key")


def test_generate_runway_success():
    g = _make_generator()
    with patch.object(g, "_call_runway", return_value={"success": True, "provider": "runway", "job_id": "123", "video_url": "http://video"}) as mocked:
        result = g.generate("a cat dancing", provider="runway")
    assert result["success"] is True
    assert result["provider"] == "runway"
    mocked.assert_called_once()


def test_generate_kling_falls_back_to_runway_on_failure():
    g = _make_generator()
    with patch.object(g, "_call_kling", side_effect=RuntimeError("kling down")):
        result = g.generate("a dog", provider="kling")

    assert result["success"] is True
    assert result["provider"] == "kling-stub"
    assert result["mock"] is True


def test_generate_runway_stub_when_key_missing():
    g = VideoGenerator(runway_api_key="", kling_api_key="kling-key")
    result = g.generate("story", provider="runway")
    assert result["success"] is True
    assert result["provider"] == "runway-stub"
    assert result["job_id"] == "stub-job"


def test_generate_auto_selects_runway():
    g = VideoGenerator(runway_api_key="runway-key", kling_api_key="")
    with patch.object(g, "_call_runway", return_value={"success": True, "provider": "runway", "job_id": "1", "video_url": "http://v"}) as mocked:
        result = g.generate("sunset")
    mocked.assert_called_once()
    assert result["provider"] == "runway"
