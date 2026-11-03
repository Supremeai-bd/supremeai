"""
Tests for services/video_to_code_pipeline.py
Focus: constants, format detection, and fallback behaviour.
Wave-3 perf: ffmpeg extraction now runs via async subprocess (event-loop safe).
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import pytest

from services.video_to_code_pipeline import (
    FRAME_INTERVAL_SECONDS,
    MAX_VIDEO_SIZE_MB,
    VIDEO_CACHE_TTL,
    UIComponent,
    VideoFormat,
    VideoFrameExtractor,
)


def test_constants():
    assert FRAME_INTERVAL_SECONDS == 2
    assert MAX_VIDEO_SIZE_MB == 50
    assert VIDEO_CACHE_TTL == 3600


def test_video_format_enum_values():
    assert VideoFormat.MP4 == "mp4"
    assert VideoFormat.AUTO == "auto"


def test_ui_component_dataclass():
    c = UIComponent(
        id="c1",
        component_type="button",
        framework_hint="react",
        position=(10, 20, 100, 40),
        properties={"label": "Submit"},
        detected_text="Submit",
    )
    assert c.component_type == "button"
    assert c.position == (10, 20, 100, 40)


def test_video_frame_extractor_check_ffmpeg_false(monkeypatch):
    extractor = VideoFrameExtractor()

    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", fake_run)
    assert extractor._check_ffmpeg() is False


@pytest.mark.anyio
async def test_extract_frames_refuses_honestly_when_no_ffmpeg(tmp_path, monkeypatch):
    """Issue #449 honest-failure contract.

    The old "fallback" passed the raw video file to the vision model as an
    "image" (guaranteed garbage advertised as success). extract_frames must
    now REFUSE with a clear error when ffmpeg is unavailable.
    """
    extractor = VideoFrameExtractor()

    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("subprocess.run", fake_run)
    video = tmp_path / "vid.mp4"
    video.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="ffmpeg is not available"):
        await extractor.extract_frames(str(video), max_frames=3)


@pytest.mark.anyio
async def test_fallback_extract_method_is_removed(tmp_path):
    """Issue #449: calling the removed fallback raises instead of faking data."""
    from services.video_to_code_pipeline import VideoToCodePipeline  # noqa: F401

    extractor = VideoFrameExtractor()
    with pytest.raises(RuntimeError, match="removed"):
        await extractor._fallback_extract(str(tmp_path / "vid.mp4"), 3)


@pytest.mark.anyio
async def test_process_video_reports_honest_failure_on_error_marker(tmp_path, monkeypatch):
    """Issue #449: error-marker code must not be reported as status=success."""
    from fastapi import HTTPException

    from services.video_to_code_pipeline import CodeGenerationResult, get_video_pipeline

    pipeline = get_video_pipeline()

    async def fake_process(video_path, framework, styling, interval=2):
        return CodeGenerationResult(
            component_tree=[],
            generated_code="// Error generating code: simulated failure",
            framework=framework,
            styling=styling,
            confidence=0.4,
            error="simulated failure",
        )

    monkeypatch.setattr(pipeline, "process", fake_process)

    from unittest.mock import AsyncMock

    from services.video_to_code_pipeline import process_video  # noqa: F811

    upload = AsyncMock()
    upload.content_type = "video/mp4"
    upload.filename = "vid.mp4"
    upload.read = AsyncMock(return_value=b"fake")

    with pytest.raises(HTTPException) as exc_info:
        await process_video(file=upload, framework="react", styling="tailwind")
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["error"] == "VIDEO_CODE_GENERATION_FAILED"


# ---------------------------------------------------------------------------
# Wave-3 perf — blocking subprocess.run() ইভেন্ট লুপ ফ্রিজ করত, তাই
# extract_frames এখন asyncio.create_subprocess_exec + await communicate() চালায়।
# এই টেস্টগুলো নতুন async পাথের আচরণ-contract lock করে (argument construction,
# error capture, timeout kill) — বাস্তব ffmpeg ছাড়াই, fake proc দিয়ে।
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode: int = 0, communicate_result: tuple = (b"", b"")) -> None:
        self.returncode = returncode
        self._communicate_result = communicate_result
        self.killed = False

    async def communicate(self) -> tuple:
        return self._communicate_result

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return 0


def _video_file(tmp_path) -> str:
    video = tmp_path / "vid.mp4"
    video.write_bytes(b"fake")
    return str(video)


@pytest.mark.anyio
async def test_extract_frames_runs_ffmpeg_via_async_subprocess(tmp_path, monkeypatch):
    extractor = VideoFrameExtractor()
    monkeypatch.setattr(extractor, "_check_ffmpeg", lambda: True)

    captured: dict[str, Any] = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _FakeProc(returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    video = _video_file(tmp_path)
    out_dir = tmp_path / "frames_vid"  # আগের মতোই output-dir naming (frames_<stem>)
    out_dir.mkdir()
    (out_dir / "frame_000.jpg").write_bytes(b"jpg0")

    frames = await extractor.extract_frames(str(video), max_frames=3)
    assert frames == [str(out_dir / "frame_000.jpg")]
    assert captured["args"][0] == "ffmpeg"
    assert f"fps=1/{FRAME_INTERVAL_SECONDS}" in captured["args"]
    assert "-vframes" in captured["args"]


@pytest.mark.anyio
async def test_extract_frames_nonzero_exit_raises_honestly(tmp_path, monkeypatch):
    # বাংলা: issue #449 — আগে error path চুপচাপ [] ফেরত দিত (dishonest);
    # এখন RuntimeError তোলে যাতে route টা 503 দেয়, success নয়।
    extractor = VideoFrameExtractor()
    monkeypatch.setattr(extractor, "_check_ffmpeg", lambda: True)

    async def fake_exec(*args, **kwargs):
        return _FakeProc(returncode=1, communicate_result=(b"", b"decode failure"))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(RuntimeError, match="Frame extraction failed"):
        await extractor.extract_frames(_video_file(tmp_path), max_frames=2)


@pytest.mark.anyio
async def test_extract_frames_timeout_kills_child_process(tmp_path, monkeypatch):
    # বাংলা: timeout-এ আগে subprocess.run নিজেই child মারত — এখন আমরা করি, নইলে zombie
    extractor = VideoFrameExtractor()
    monkeypatch.setattr(extractor, "_check_ffmpeg", lambda: True)

    proc_holder: dict[str, _FakeProc] = {}

    class _TimeoutProc(_FakeProc):
        async def communicate(self):
            raise TimeoutError  # asyncio.wait_for-ও এই builtin TimeoutError-ই তোলে (py3.11+)

    async def fake_exec(*args, **kwargs):
        proc = _TimeoutProc()
        proc_holder["proc"] = proc
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    # Issue #449: timeout no longer returns [] — it raises after killing the
    # child (no zombie processes, honest failure).
    with pytest.raises(RuntimeError, match="Frame extraction failed"):
        await extractor.extract_frames(_video_file(tmp_path), max_frames=2)
    assert proc_holder["proc"].killed is True


@pytest.mark.anyio
async def test_extract_frames_file_not_found_propagates(tmp_path, monkeypatch):
    # বাংলা: আগের subprocess.run-ও FileNotFoundError ধরত না (check-এর পরে ffmpeg গায়েব
    # হলে) — নতুন async পাথেও সেই semantics অক্ষুণ্ণ, catch তালিকা একই রাখা হয়েছে
    extractor = VideoFrameExtractor()
    monkeypatch.setattr(extractor, "_check_ffmpeg", lambda: True)

    async def fake_exec(*args, **kwargs):
        raise FileNotFoundError("ffmpeg vanished")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    with pytest.raises(FileNotFoundError):
        await extractor.extract_frames(_video_file(tmp_path), max_frames=2)


def test_called_process_error_is_subprocess_error():
    # বাংলা: নতুন কোডে raise করা CalledProcessError বাইরের except-এ ধরা পড়ে —
    # এই অ্যাসারশন সেই সম্পর্কটা ভবিষ্যতে ভাঙা থেকে রক্ষা করে
    assert issubclass(subprocess.CalledProcessError, subprocess.SubprocessError)
