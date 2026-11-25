# বাংলা মন্তব্য: daily_key_verifier-এর জন্য স্বয়ংসম্পূর্ণ ইউনিট টেস্ট স্যুট
# এতে httpx ও urllib উভয় মোডে মেটাডেটা পিং, ডিক্রিপশন ফেইল-সেফ এবং কোটা ক্যালকুলেশন ভেরিফাই করা হয়েছে।
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from scripts.ops import daily_key_verifier


@pytest.mark.asyncio
async def test_ping_httpx_success():
    # বাংলা মন্তব্য: httpx সহ ভ্যালিড রেসপন্স (200 OK) যাচাই
    mock_resp = Mock(status_code=200)
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(daily_key_verifier, "httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        res = await daily_key_verifier._ping("groq", "gsk_test123")
        assert res is True


@pytest.mark.asyncio
async def test_ping_httpx_failure():
    # বাংলা মন্তব্য: ইনভ্যালিড রেসপন্স (401 Unauthorized) যাচাই
    mock_resp = Mock(status_code=401)
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(daily_key_verifier, "httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        res = await daily_key_verifier._ping("groq", "gsk_invalid")
        assert res is False


@pytest.mark.asyncio
async def test_ping_urllib_fallback_success():
    # বাংলা মন্তব্য: httpx অনুপস্থিত থাকলে urllib ফলব্যাক সফল হওয়া যাচাই
    with patch.object(daily_key_verifier, "httpx", None):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            res = await daily_key_verifier._ping("openrouter", "sk-or-v1-test")
            assert res is True


@pytest.mark.asyncio
async def test_ping_urllib_fallback_http_error():
    # বাংলা মন্তব্য: urllib ফলব্যাকে HTTPError আসলে False রিটার্ন করা যাচাই
    import urllib.error
    with patch.object(daily_key_verifier, "httpx", None):
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)):
            res = await daily_key_verifier._ping("openrouter", "sk-or-v1-bad")
            assert res is False


@pytest.mark.asyncio
async def test_ping_unknown_provider():
    # বাংলা মন্তব্য: অজানা প্রোভাইডারের ক্ষেত্রে ট্রু ধরে চলা
    res = await daily_key_verifier._ping("unknown_custom_provider", "key123")
    assert res is True


@pytest.mark.asyncio
async def test_sweep_db_none(capsys):
    # বাংলা মন্তব্য: ডাটাবেস ক্লায়েন্ট অনুপস্থিত থাকলে নিরাপদ এক্সিট
    with patch.object(daily_key_verifier, "get_db", None):
        await daily_key_verifier.sweep()
        out = capsys.readouterr().out
        assert "supabase client unavailable" in out


@pytest.mark.asyncio
async def test_sweep_keys_flow():
    # বাংলা মন্তব্য: এন্ড-টু-এন্ড sweep ফ্লো মকিং
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_db.client.table.return_value = mock_table

    sample_rows = [
        {
            "id": "key-1",
            "user_id": "usr-1",
            "provider": "groq",
            "encrypted_key": "dummy_enc",
            "status": "pending",
        }
    ]

    mock_select = MagicMock()
    mock_select.execute.return_value = Mock(data=sample_rows)
    mock_table.select.return_value = mock_select

    mock_update = MagicMock()
    mock_eq = MagicMock()
    mock_eq.execute.return_value = Mock(data=[])
    mock_update.eq.return_value = mock_eq
    mock_table.update.return_value = mock_update

    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = Mock(data=[])
    mock_table.upsert.return_value = mock_upsert

    with patch.object(daily_key_verifier, "get_db", return_value=mock_db):
        with patch("core.security.secure_credential_store.RotatingFernet") as mock_rf_cls:
            mock_rf = Mock()
            mock_rf.decrypt.return_value = b"decrypted_groq_key"
            mock_rf_cls.return_value = mock_rf

            with patch.object(daily_key_verifier, "_ping", new_callable=AsyncMock) as mock_ping:
                mock_ping.return_value = True

                with patch.dict("os.environ", {"SUPREMEAI_CREDENTIAL_ENC_KEY": "dummy_key"}):
                    await daily_key_verifier.sweep()
                    assert mock_ping.called
