"""Task-12 test coverage expansion — session SSE stream contract tests.

বাংলা: GET /api/session/{session_id}/stream — এই SSE এন্ডপয়েন্টটি আগে
অরফান ছিল (কোনো টেস্ট নেই; frontend SessionDetailPage ককপিট নিজেও dead
ছিল)। Task-12 ghost activation-এ ককপিটটি /sessions/:sessionId route-এ
mounted হওয়ায় এন্ডপয়েন্টের প্রকৃত কনট্র্যাক্ট lock করা হলো: প্রথমে
"connected" system ইভেন্ট, তারপর batcher-এ publish করা লগ ইভেন্ট
logs/state/reasoning/filetree চ্যানেলে ফ্যানআউট।

বাংলা নোট: টেস্টগুলো ইচ্ছাকৃতভাবে endpoint-এর ভেতরের event_generator-কে
সরাসরি drive করে (fake Request দিয়ে) — TestClient-এর httpx transport SSE
stream বাফার করে অনির্দিষ্টকালের জন্য আটকে যায়; generator-level টেস্ট
deterministic এবং CI-এ hang-মুক্ত। প্রতিটি টেস্টে publisher আলাদা task-এ
চলে — কারণ generator queue.get()-এ ব্লক অবস্থায় থাকলে একই task থেকে
publish করা সম্ভব নয়।
"""

from __future__ import annotations

import asyncio
import json

import pytest


class _FakeRequest:
    """stream_session-এর ব্যবহৃত Request surface-এর সর্বনিম্ন স্টাব।"""

    async def is_disconnected(self) -> bool:  # pragma: no cover - trivial
        return False


async def _drive_stream(session_id: str, published_entry: dict) -> list[dict]:
    """Open the real SSE generator, read 2 frames (connected + published)."""
    from api.routes.session_stream import stream_session
    from core.observability.log_batcher import batcher

    response = await stream_session(_FakeRequest(), session_id)  # type: ignore[arg-type]
    frames: list[dict] = []

    # বাংলা: প্রথম ফ্রেম = সংযোগ মাত্রই honest "connected" system ইভেন্ট
    first = await response.body_iterator.__anext__()
    frames.append(first)

    # বাংলা: generator queue.get()-এ অপেক্ষা করার সময় আলাদা task থেকে publish
    async def _publisher() -> None:
        await asyncio.sleep(0.05)
        batcher.publish(session_id, published_entry)

    pub = asyncio.create_task(_publisher())
    second = await response.body_iterator.__anext__()
    frames.append(second)
    await pub

    # বাংলা: স্ট্রিম বন্ধ করলে generator-এর finally unsubscribe + auto-save
    # hook চালু হয়; বাফার খালি বলে auto-save সঙ্গে সঙ্গে ফেরত যায়।
    await response.body_iterator.aclose()
    await asyncio.sleep(0)
    return frames


def _frames_json(frames: list[dict]) -> list[dict]:
    parsed = []
    for f in frames:
        parsed.append({"event": f.get("event"), "data": json.loads(f["data"])})
    return parsed


class TestSessionStream:
    @pytest.mark.asyncio
    async def test_stream_sends_connected_then_forwards_published_log(self):
        frames = await _drive_stream(
            "test-session-1",
            {"log_type": "info", "session_id": "test-session-1", "msg": "hello"},
        )
        parsed = _frames_json(frames)
        assert parsed[0]["event"] == "connected"
        assert parsed[0]["data"]["channel"] == "system"

        # বাংলা: publish করা লগ logs চ্যানেলে ফ্যানআউট হবে (SSE-only path)
        assert parsed[1]["data"]["channel"] == "logs"
        assert parsed[1]["data"]["data"]["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_stream_routes_state_change_to_state_channel(self):
        frames = await _drive_stream(
            "test-session-2",
            {"log_type": "state_change", "current_state": "executing"},
        )
        (second,) = _frames_json(frames)[1:]
        assert second["data"]["channel"] == "state"
        assert second["data"]["data"]["current_state"] == "executing"

    @pytest.mark.asyncio
    async def test_stream_routes_reasoning_step_to_reasoning_channel(self):
        frames = await _drive_stream(
            "test-session-3",
            {"log_type": "reasoning_step", "step": 1, "token": "thinking..."},
        )
        (second,) = _frames_json(frames)[1:]
        assert second["data"]["channel"] == "reasoning"
        assert second["data"]["data"]["token"] == "thinking..."

    @pytest.mark.asyncio
    async def test_stream_routes_file_events_to_filetree_channel(self):
        frames = await _drive_stream(
            "test-session-4",
            {"log_type": "file_write", "path": "src/a.py", "content": "x"},
        )
        (second,) = _frames_json(frames)[1:]
        assert second["data"]["channel"] == "filetree"
        assert second["data"]["data"]["path"] == "src/a.py"
