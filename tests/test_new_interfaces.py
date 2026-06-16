import os
from unittest.mock import MagicMock, patch
import pytest
from interfaces.voice import VoiceInterface
from interfaces.discord_bot import SupremeDiscordBot

def test_voice_interface_stt_missing_file():
    vi = VoiceInterface()
    res = vi.speech_to_text("non_existent_file.wav")
    assert res == ""

@patch("httpx.post")
def test_voice_interface_stt_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "hello world"}
    mock_post.return_value = mock_response

    # Create dummy file
    dummy_path = "tests/dummy_audio.wav"
    os.makedirs("tests", exist_ok=True)
    with open(dummy_path, "wb") as f:
        f.write(b"dummy audio data")

    try:
        os.environ["HF_API_KEY"] = "mock_key"
        vi = VoiceInterface()
        res = vi.speech_to_text(dummy_path)
        assert res == "hello world"
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

def test_discord_bot_initialization():
    bot = SupremeDiscordBot()
    assert bot is not None
