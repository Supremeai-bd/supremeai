import os
import httpx
from loguru import logger
from config import settings

class VoiceInterface:
    """
    Handles Voice Interactions:
    - Speech-to-Text (STT) via HuggingFace Whisper Inference API (Free & Fast)
    - Text-to-Speech (TTS) via HuggingFace / public TTS APIs or fallback
    """
    def __init__(self):
        self.hf_token = os.getenv("HF_API_KEY", settings.hf_api_key)
        self.api_url = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"
        
    def speech_to_text(self, audio_path: str) -> str:
        """Transcribes audio file to text using Whisper API."""
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return ""
            
        if not self.hf_token:
            logger.warning("HF_API_KEY not set. Cannot transcribe audio.")
            return "Error: HuggingFace API key is missing."
            
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        try:
            with open(audio_path, "rb") as f:
                data = f.read()
            response = httpx.post(self.api_url, headers=headers, content=data, timeout=30.0)
            if response.status_code == 200:
                result = response.json()
                transcription = result.get("text", "")
                logger.info(f"Transcribed audio: {transcription}")
                return transcription
            else:
                logger.error(f"Whisper API error: {response.status_code} - {response.text}")
                return f"Error transcribing audio (status code: {response.status_code})"
        except Exception as e:
            logger.error(f"Exception during speech to text: {e}")
            return f"Error: {str(e)}"

    def text_to_speech(self, text: str, output_path: str = "data/output.mp3") -> bool:
        """Converts text to speech and saves to output_path."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Using free public TTS service
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={httpx.encode(text)}"
        try:
            response = httpx.get(tts_url)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Generated speech file at: {output_path}")
                return True
            else:
                logger.error(f"TTS service returned status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Exception during text to speech: {e}")
            return False
