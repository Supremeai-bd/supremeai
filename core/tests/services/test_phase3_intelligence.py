"""
Unit tests for Phase 3 Intelligence Features:
- SyntheticDataPipeline instruction-tuning dataset export
- LearningLoop EWC loss penalty calculation
- VoiceService STT and TTS synthesis
- VisionService image and diagram analysis
"""

import pytest

from adaptive_engine.learning_loop import LearningLoop
from pipelines.synthetic_data_pipeline import SyntheticDataPipeline
from services.vision_service import VisionService
from services.voice_service import VoiceService


@pytest.mark.asyncio
async def test_synthetic_data_pipeline(tmp_path):
    pipeline = SyntheticDataPipeline()
    out_path = tmp_path / "test_ft.jsonl"
    result = await pipeline.generate_dataset(output_path=str(out_path))
    assert result["status"] == "success"
    assert out_path.exists()


def test_ewc_loss_penalty():
    loop = LearningLoop()
    cur_weights = {"w1": 0.5, "w2": 0.9}
    old_weights = {"w1": 0.4, "w2": 0.9}
    fisher = {"w1": 1.0, "w2": 1.0}
    penalty = loop.compute_ewc_loss_penalty(cur_weights, old_weights, fisher, ewc_lambda=0.5)
    assert penalty > 0.0


@pytest.mark.asyncio
async def test_voice_service(monkeypatch):
    """Honest voice contract (issue #445).

    Without any provider configured the service must return an explicit
    'unavailable' status — NEVER a fabricated transcript or placeholder audio.
    Real provider paths are covered with mocks (no network in unit tests).
    """
    import sys

    from core.config import settings

    voice = VoiceService()

    # --- Unavailable path: no STT/TTS provider configured ---
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.delenv("HF_API_KEY", raising=False)
    monkeypatch.setattr(settings, "groq_api_key", "", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(settings, "hf_api_key", "", raising=False)
    # NOTE: Settings has no elevenlabs_api_key field — voice_service reads it
    # via getattr(..., default) so clearing the env var alone is sufficient.
    # Block the edge-tts import (keyless real TTS) so the fallback is honest.
    monkeypatch.setitem(sys.modules, "edge_tts", None)

    stt_res = await voice.speech_to_text(b"fake_wav_data")
    assert stt_res["status"] == "unavailable"
    assert stt_res["reason"] == "STT_NOT_CONFIGURED"
    assert stt_res["transcript"] == ""

    tts_res = await voice.text_to_speech("সুপ্রিম এআই সিস্টেমে আপনাকে স্বাগতম।")
    assert tts_res["status"] == "unavailable"
    assert tts_res["reason"] == "TTS_NOT_CONFIGURED"

    # --- Real provider paths (mocked — contract/routing only) ---
    async def fake_groq(audio_bytes, filename, api_key):
        assert audio_bytes == b"fake_wav_data"
        return {"status": "success", "transcript": "hello world", "model": "whisper-large-v3"}

    monkeypatch.setattr(VoiceService, "_transcribe_with_groq", staticmethod(fake_groq))
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    stt_ok = await voice.speech_to_text(b"fake_wav_data")
    assert stt_ok["status"] == "success"
    assert stt_ok["transcript"] == "hello world"

    async def fake_edge(text, lang):
        return {
            "status": "success",
            "audio_bytes": b"RIFF-real",
            "audio_bytes_length": 8,
            "mime_type": "audio/mpeg",
        }

    monkeypatch.setattr(VoiceService, "_tts_with_edge", staticmethod(fake_edge))
    tts_ok = await voice.text_to_speech("হ্যালো")
    assert tts_ok["status"] == "success"
    assert tts_ok["audio_bytes_length"] > 0


@pytest.mark.asyncio
async def test_vision_service(monkeypatch):
    """Honest vision contract (issue #444).

    Without a vision provider the service must return an explicit
    'unavailable' status — NEVER a hardcoded description with fake confidence.
    The real Gemini path is covered with a mock (no network in unit tests).
    """
    from core.config import settings

    vision = VisionService()

    # --- Unavailable path: no vision provider configured ---
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)

    res = await vision.analyze_image(b"fake_image_bytes", query="Analyze architecture")
    assert res["status"] == "unavailable"
    assert res["reason"] == "VISION_NOT_CONFIGURED"
    assert res["analysis"] == ""

    # --- Real Gemini path (mocked — contract/routing only) ---
    async def fake_gemini(image_bytes, query, user_query, api_key):
        assert image_bytes == b"fake_image_bytes"
        return {
            "status": "success",
            "analysis": "identified a three-tier architecture diagram",
            "model": "gemini-test",
        }

    monkeypatch.setattr(VisionService, "_analyze_with_gemini", staticmethod(fake_gemini))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    ok = await vision.analyze_image(b"fake_image_bytes", query="Analyze architecture")
    assert ok["status"] == "success"
    assert "architecture" in ok["analysis"].lower()
