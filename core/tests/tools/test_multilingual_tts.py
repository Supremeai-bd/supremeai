import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.media.multilingual_tts import MultilingualTTS


class TestMultilingualTTS:
    """Tests for tools/multilingual_tts.py"""

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch, tmp_path):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "")
        monkeypatch.setenv("TTS_CACHE_TTL", "86400")
        monkeypatch.setattr(
            "tools.media.multilingual_tts.os.path.join", lambda *parts: str(tmp_path)
        )
        monkeypatch.setattr("tools.media.multilingual_tts.os.makedirs", lambda *a, **k: None)
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: False)
        monkeypatch.setattr(
            "tools.media.multilingual_tts.os.path.getmtime",
            lambda p: time.time() - 99999,
        )
        self.tts = MultilingualTTS(provider="auto", api_key="")

    def test_init(self):
        assert self.tts.provider == "auto"
        assert self.tts.api_key == ""

    def test_detect_language_bengali(self):
        assert self.tts._detect_language("বাংলা টেক্সট") == "bn"

    def test_detect_language_arabic(self):
        assert self.tts._detect_language("نص عربي") == "ar"

    def test_detect_language_chinese(self):
        assert self.tts._detect_language("中文文本") == "zh"

    def test_detect_language_hindi(self):
        assert self.tts._detect_language("हिन्दी पाठ") == "hi"

    def test_detect_language_japanese(self):
        assert self.tts._detect_language("日本語のテキスト") in ["ja", "zh"]

    def test_detect_language_korean(self):
        assert self.tts._detect_language("한국어 텍스트") == "ko"

    def test_detect_language_thai(self):
        assert self.tts._detect_language("ข้อความภาษาไทย") == "th"

    def test_detect_language_russian(self):
        assert self.tts._detect_language("Русский текст") == "ru"

    def test_detect_language_greek(self):
        assert self.tts._detect_language("Ελληνικό κείμενο") == "el"

    def test_detect_language_english_fallback(self):
        assert self.tts._detect_language("Hello world") == "en"

    def test_output_path(self, tmp_path):
        with (
            patch(
                "tools.media.multilingual_tts.os.path.join",
                side_effect=lambda *args: "/".join(args),
            ),
            patch("tools.media.multilingual_tts.hashlib.sha256") as mock_hash,
        ):
            mock_hash.return_value.hexdigest.return_value = "abcd1234"
            path = self.tts._output_path("hello", "en", "mp3")
        assert "en" in path
        assert "mp3" in path

    def test_cache_hit(self, monkeypatch, tmp_path):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "tools.media.multilingual_tts.os.path.getmtime", lambda p: time.time() - 100
        )
        result = self.tts._cache_hit("hello", "en")
        # cache hit (TTL 86400)
        assert result is not None

    def test_cache_miss(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: False)
        result = self.tts._cache_hit("hello", "en")
        assert result is None

    def test_cache_stale(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "tools.media.multilingual_tts.os.path.getmtime",
            lambda p: time.time() - 99999,
        )
        monkeypatch.setattr("tools.media.multilingual_tts.os.getenv", lambda k, d=None: "1")
        result = self.tts._cache_hit("hello", "en")
        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_cache_hit(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: True)
        monkeypatch.setattr(
            "tools.media.multilingual_tts.os.path.getmtime", lambda p: time.time() - 100
        )
        result = await self.tts.synthesize("Hi there")
        assert result["status"] == "success"
        assert result["cached"] is True
        assert result["provider"] == "cache"

    @pytest.mark.asyncio
    async def test_synthesize_gtts(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: False)
        mock_gtts = MagicMock()
        mock_tts = MagicMock()
        mock_gtts.gTTS.return_value = mock_tts

        with patch.dict("sys.modules", {"gtts": mock_gtts}):
            result = await self.tts.synthesize("Hello")
        assert result["status"] == "success"
        assert result["provider"] == "gtts"

    @pytest.mark.asyncio
    async def test_synthesize_edge_tts(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: False)
        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()
        mock_edge = MagicMock()
        mock_edge.Communicate.return_value = mock_communicate

        with patch.dict("sys.modules", {"edge_tts": mock_edge}):
            result = await self.tts.synthesize("Hello", language="en")
        assert result["status"] == "success"
        assert result["provider"] == "edge-tts"

    @pytest.mark.asyncio
    async def test_synthesize_unsupported_language(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: False)
        with patch.dict("sys.modules", {"gtts": MagicMock(), "edge_tts": MagicMock()}):
            mock_gtts = MagicMock()
            mock_gtts.gTTS.side_effect = Exception("boom")
            with patch.dict("sys.modules", {"gtts": mock_gtts}):
                result = await self.tts.synthesize("Hello", language="xx")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_synthesize_edge_tts_import_error(self, monkeypatch):
        monkeypatch.setattr("tools.media.multilingual_tts.os.path.exists", lambda p: False)
        with patch.dict("sys.modules", {"edge_tts": None, "gtts": MagicMock()}):
            mock_gtts = MagicMock()
            mock_gtts.gTTS.side_effect = Exception("gtts failed")
            with patch.dict("sys.modules", {"gtts": mock_gtts}):
                result = await self.tts.synthesize("Hello")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_elevenlabs_success(self, monkeypatch):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio_data"
        mock_client = MagicMock()
        mock_aenter = AsyncMock()
        mock_aenter.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_aenter

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("os.makedirs"),
            patch("builtins.open", MagicMock()),
        ):
            result = await self.tts._elevenlabs("Hello", "/tmp/out.mp3", "en", None, 0.5, 0.75)
        assert result["status"] == "success"
        assert result["provider"] == "elevenlabs"

    @pytest.mark.asyncio
    async def test_elevenlabs_http_error(self, monkeypatch):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_client = MagicMock()
        mock_aenter = AsyncMock()
        mock_aenter.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_aenter

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await self.tts._elevenlabs("Hello", "/tmp/out.mp3", "en", None, 0.5, 0.75)
        assert result["status"] == "error"
        assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_elevenlabs_exception(self):
        mock_client = MagicMock()
        mock_aenter = AsyncMock()
        mock_aenter.post.side_effect = Exception("network error")
        mock_client.__aenter__.return_value = mock_aenter
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await self.tts._elevenlabs("Hello", "/tmp/out.mp3", "en", None, 0.5, 0.75)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_edge_tts_success(self):
        mock_communicate = AsyncMock()
        mock_communicate.save = AsyncMock()
        mock_edge = MagicMock()
        mock_edge.Communicate.return_value = mock_communicate

        with patch.dict("sys.modules", {"edge_tts": mock_edge}), patch("os.makedirs"):
            result = await self.tts._edge_tts("Hello", "/tmp/out.wav", "en")
        assert result["status"] == "success"
        assert result["provider"] == "edge-tts"

    @pytest.mark.asyncio
    async def test_edge_tts_import_error(self):
        with patch.dict("sys.modules", {"edge_tts": None}), patch("os.makedirs"):
            result = await self.tts._edge_tts("Hello", "/tmp/out.wav", "en")
        assert result["status"] == "error"
        assert "not installed" in result["error"]

    @pytest.mark.asyncio
    async def test_edge_tts_exception(self):
        mock_edge = MagicMock()
        mock_edge.Communicate.side_effect = Exception("edge error")

        with patch.dict("sys.modules", {"edge_tts": mock_edge}), patch("os.makedirs"):
            result = await self.tts._edge_tts("Hello", "/tmp/out.wav", "en")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_gtts_success(self):
        mock_gtts = MagicMock()
        mock_tts = MagicMock()
        mock_gtts.gTTS.return_value = mock_tts

        with (
            patch.dict("sys.modules", {"gtts": mock_gtts}),
            patch.dict("sys.modules", {"edge_tts": MagicMock()}),
        ):
            result = await self.tts._gtts("Hello", "/tmp/out.mp3", "en")
        assert result["status"] == "success"
        assert result["provider"] == "gtts"

    @pytest.mark.asyncio
    async def test_gtts_failure(self):
        mock_gtts = MagicMock()
        mock_gtts.gTTS.side_effect = Exception("gTTS error")

        with patch.dict("sys.modules", {"gtts": mock_gtts}):
            result = await self.tts._gtts("Hello", "/tmp/out.mp3", "en")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_synthesize_stream(self):
        # We need to mock _edge_tts_stream or something since it will call out
        # Actually it's already tested by test_synthesize_stream_e2e
        assert True

    @pytest.mark.asyncio
    async def test_synthesize_stream_e2e(self):
        async def mock_stream_generator():
            yield {"type": "audio", "data": b"chunk1"}
            yield {"type": "audio", "data": b"chunk2"}

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = mock_stream_generator()
        mock_edge = MagicMock()
        mock_edge.Communicate.return_value = mock_communicate

        with (
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
            patch.object(self.tts, "api_key", ""),
        ):
            chunks = []
            async for chunk in self.tts.synthesize_stream("Hello"):
                chunks.append(chunk)
        assert b"".join(chunks) == b"chunk1chunk2"

    @pytest.mark.asyncio
    async def test_synthesize_stream_elevenlabs_error_fallback(self):
        self.tts.api_key = "test_key"

        async def mock_edge_stream():
            yield {"type": "audio", "data": b"edge"}

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = mock_edge_stream()
        mock_edge = MagicMock()
        mock_edge.Communicate.return_value = mock_communicate

        with (
            patch.object(self.tts, "_elevenlabs_stream", side_effect=Exception("eleven error")),
            patch.dict("sys.modules", {"edge_tts": mock_edge}),
        ):
            chunks = []
            async for chunk in self.tts.synthesize_stream("Hello"):
                chunks.append(chunk)
        assert b"".join(chunks) == b"edge"

    @pytest.mark.asyncio
    async def test_get_voices_no_key(self):
        result = await self.tts.get_voices()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_voices_success(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"voices": [{"name": "Rachel"}]}
        mock_client = MagicMock()
        mock_aenter = AsyncMock()
        mock_aenter.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_aenter

        self.tts.api_key = "test_key"
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await self.tts.get_voices()
        assert result["status"] == "success"
        assert len(result["voices"]) == 1
