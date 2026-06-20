import os
import pytest
from unittest.mock import patch, MagicMock
from tools.bangla_voice import BanglaVoice, BanglaVoiceResult

def test_bangla_voice_init():
    with patch("tools.bangla_voice.BanglaVoice._check_stt_available", return_value=True), \
         patch("tools.bangla_voice.BanglaVoice._check_tts_available", return_value=True):
        voice = BanglaVoice()
        assert voice._stt_available
        assert voice._tts_available

def test_bangla_voice_transcribe_not_found():
    voice = BanglaVoice()
    with pytest.raises(FileNotFoundError):
        voice.transcribe("non_existent.wav")

def test_bangla_voice_transcribe_whisper():
    mock_whisper = MagicMock()
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"text": "আমার সোনার বাংলা"}
    mock_whisper.load_model.return_value = mock_model
    
    with patch("tools.bangla_voice.os.path.exists", return_value=True), \
         patch("tools.bangla_voice.BanglaVoice._check_stt_available", return_value=True), \
         patch("sys.modules", {"whisper": mock_whisper}):
        
        voice = BanglaVoice()
        res = voice.transcribe("dummy.wav")
        assert res.text == "আমার সোনার বাংলা"
        assert res.source == "whisper"

def test_bangla_voice_speak_gtts():
    mock_gtts = MagicMock()
    mock_tts_obj = MagicMock()
    mock_gtts.gTTS.return_value = mock_tts_obj
    
    with patch("tools.bangla_voice.BanglaVoice._check_tts_available", return_value=False), \
         patch("sys.modules", {"gtts": mock_gtts}):
        
        voice = BanglaVoice()
        res = voice.speak("কেমন আছেন?", "output.mp3")
        assert res.text == "কেমন আছেন?"
        assert res.source == "gtts"
        mock_tts_obj.save.assert_called_with("output.mp3")

def test_bangla_voice_speak_coqui():
    mock_tts_class = MagicMock()
    mock_tts_obj = MagicMock()
    mock_tts_class.return_value = mock_tts_obj
    
    with patch("tools.bangla_voice.BanglaVoice._check_tts_available", return_value=True), \
         patch("sys.modules", {"TTS.api": MagicMock(TTS=mock_tts_class)}):
        
        voice = BanglaVoice(prefer_coqui=True)
        res = voice.speak("শুভ সকাল", "output.mp3")
        assert res.text == "শুভ সকাল"
        assert res.source == "coqui"
        mock_tts_obj.tts_to_file.assert_called_with(text="শুভ সকাল", file_path="output.mp3")
