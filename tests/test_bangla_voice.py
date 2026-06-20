import os
from unittest.mock import patch, MagicMock
from tools.bangla_voice import BanglaVoice, BanglaVoiceResult


def test_speak_gtts_success():
    voice = BanglaVoice.__new__(BanglaVoice)
    voice.prefer_coqui = False
    voice._stt_available = False
    voice._tts_available = False

    fake_tts = MagicMock()
    fake_tts.save.return_value = None

    with patch("tools.bangla_voice.gTTS", return_value=fake_tts) as mock_gtts:
        result = voice.speak("হ্যালো", output_path="out.mp3")

    assert isinstance(result, BanglaVoiceResult)
    assert result.text == "হ্যালো"
    assert result.language == "bn"
    mock_gtts.assert_called_once_with(text="হ্যালো", lang="bn")
    fake_tts.save.assert_called_once_with("out.mp3")


def test_transcribe_uses_whisper():
    voice = BanglaVoice.__new__(BanglaVoice)
    voice.prefer_coqui = False
    voice._stt_available = True
    voice._tts_available = False

    fake_whisper = MagicMock()
    fake_whisper.load_model.return_value.transcribe.return_value = {"text": "নমস্কার"}

    with patch("tools.bangla_voice.whisper", fake_whisper):
        result = voice.transcribe("in.wav")

    assert result.text == "নমস্কার"
    assert result.source == "whisper"


def test_speak_empty_text_raises():
    voice = BanglaVoice.__new__(BanglaVoice)
    try:
        voice.speak("")
    except ValueError as exc:
        assert "Empty text" in str(exc)
