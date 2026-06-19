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
        """Transcribes audio file to text using Whisper (local if available, else API)."""
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return ""
            
        # Try local whisper first
        try:
            import whisper
            logger.info("Using local Whisper model for Speech-to-Text...")
            model = whisper.load_model("tiny")
            result = model.transcribe(audio_path)
            transcription = result.get("text", "").strip()
            if transcription:
                logger.info(f"Locally transcribed audio: {transcription}")
                return transcription
        except Exception as e:
            logger.warning(f"Local Whisper not available or failed: {e}. Falling back to HuggingFace API...")

        # Fallback to HuggingFace Whisper Inference API
        if not self.hf_token:
            logger.warning("HF_API_KEY not set. Cannot transcribe audio via API.")
            return "Error: HuggingFace API key is missing and local Whisper failed."
            
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        try:
            with open(audio_path, "rb") as f:
                data = f.read()
            response = httpx.post(self.api_url, headers=headers, content=data, timeout=30.0)
            if response.status_code == 200:
                result = response.json()
                transcription = result.get("text", "")
                logger.info(f"Transcribed audio via API: {transcription}")
                return transcription
            else:
                logger.error(f"Whisper API error: {response.status_code} - {response.text}")
                return f"Error transcribing audio (status code: {response.status_code})"
        except Exception as api_err:
            logger.error(f"Exception during speech to text API fallback: {api_err}")
            return f"Error: {str(api_err)}"

    def text_to_speech(self, text: str, output_path: str = "data/output.mp3") -> bool:
        """Converts text to speech and saves to output_path using Coqui TTS (offline), gTTS, or HTTP fallback."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        has_bengali = any(0x0980 <= ord(char) <= 0x09FF for char in text)
        lang = 'bn' if has_bengali else 'en'
        logger.info(f"Auto-detected language for TTS: {lang}")

        try:
            from TTS.api import TTS as CoquiTTS
            logger.info("Using Coqui TTS for offline Text-to-Speech...")
            device = "cpu"
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
            except Exception:
                pass
            tts = CoquiTTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False, audio_output_device="auto")
            if hasattr(tts, "to"):
                try:
                    tts.to(device)
                except Exception as device_err:
                    logger.warning(f"Coqui TTS device set failed ({device_err}); using default device.")
            tts.tts_to_file(text=text, file_path=output_path, language=lang)
            logger.info(f"Generated offline speech file at: {output_path}")
            return True
        except Exception as e:
            logger.warning(f"Coqui TTS unavailable or failed: {e}. Falling back to gTTS...")

        try:
            from gtts import gTTS
            logger.info("Using gTTS library for Text-to-Speech...")
            tts = gTTS(text=text, lang=lang)
            tts.save(output_path)
            logger.info(f"Generated speech file locally at: {output_path}")
            return True
        except Exception as e:
            logger.warning(f"gTTS library not available or failed: {e}. Falling back to Google TTS API...")

        import urllib.parse
        encoded_text = urllib.parse.quote(text)
        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl={lang}&client=tw-ob&q={encoded_text}"
        try:
            response = httpx.get(tts_url)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"Generated speech file via TTS API at: {output_path}")
                return True
            logger.error(f"TTS service returned status code: {response.status_code}")
            return False
        except Exception as api_err:
            logger.error(f"Exception during text to speech API fallback: {api_err}")
            return False
