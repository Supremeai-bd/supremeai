# বাংলা মন্তব্য: daily_key_verifier-এর জন্য স্বয়ংসম্পূর্ণ ইউনিট টেস্ট স্যুট
# এতে httpx ও urllib উভয় মোডে মেটাডেটা পিং, ডিক্রিপশন ফেইল-সেফ এবং কোটা ক্যালকুলেশন ভেরিফাই করা হয়েছে।
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from scripts.ops import daily_key_verifier


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code,expected", [(200, True), (401, False), (403, False), (429, None), (500, None)])
async def test_ping_httpx_responses(status_code, expected):
    # বাংলা মন্তব্য: httpx রেসপন্স স্ট্যাটাস কোড (200 বনাম 401) প্যারামিটারাইজড যাচাই
    mock_client = AsyncMock()
    mock_client.get.return_value = Mock(status_code=status_code)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(daily_key_verifier, "httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        res = await daily_key_verifier._ping("groq", "gsk_test")
        assert res is expected


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
    # বাংলা মন্তব্য: অজানা প্রোভাইডারের ক্ষেত্রে বৈধতার অনুমান করা যাবে না।
    res = await daily_key_verifier._ping("unknown_custom_provider", "key123")
    assert res is None


@pytest.mark.asyncio
async def test_sweep_db_none(capsys):
    # বাংলা মন্তব্য: ডাটাবেস ক্লায়েন্ট অনুপস্থিত থাকলে নিরাপদ এক্সিট
    with patch.object(daily_key_verifier, "get_db", None):
        assert await daily_key_verifier.sweep() is False
        assert "supabase client unavailable" in capsys.readouterr().err


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
                    assert await daily_key_verifier.sweep() is True
                    assert mock_ping.called
                    mock_rf.decrypt.assert_called_once_with(b"dummy_enc", ttl=None)


@pytest.mark.asyncio
async def test_sweep_unconfigured_client_is_failure(capsys):
    db = Mock(client=None)
    with patch.object(daily_key_verifier, "get_db", return_value=db):
        assert await daily_key_verifier.sweep() is False
    assert "supabase client unavailable" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_sweep_fetch_error_fails_without_leaking_exception(capsys):
    db = MagicMock()
    db.client.table.side_effect = RuntimeError("do-not-log-secret")
    with patch.object(daily_key_verifier, "get_db", return_value=db):
        assert await daily_key_verifier.sweep() is False
    captured = capsys.readouterr()
    assert "fetch failed" in captured.err
    assert "do-not-log-secret" not in captured.err + captured.out


@pytest.mark.asyncio
async def test_sweep_inconclusive_probe_preserves_status():
    db = MagicMock()
    keys = db.client.table.return_value
    result = Mock(data=[{"id": "k1", "user_id": "u1", "provider": "groq", "encrypted_key": "abc"}])
    keys.select.return_value.execute.return_value = result
    keys.select.return_value.eq.return_value.execute.return_value = Mock(data=[{"provider": "groq", "status": "valid"}])
    with patch.object(daily_key_verifier, "get_db", return_value=db), \
         patch("core.security.secure_credential_store.RotatingFernet") as cipher, \
         patch.object(daily_key_verifier, "_ping", new_callable=AsyncMock, return_value=None), \
         patch.dict("os.environ", {"SUPREMEAI_CREDENTIAL_ENC_KEY": "test-key"}):
        cipher.return_value.decrypt.return_value = b"key"
        assert await daily_key_verifier.sweep() is False
    keys.update.assert_not_called()


@pytest.mark.asyncio
async def test_failed_quota_refresh_never_overwrites_quota():
    db = MagicMock()
    keys = db.client.table.return_value
    keys.select.return_value.execute.return_value = Mock(data=[{"id": "k1", "user_id": "u1", "provider": "groq", "encrypted_key": "abc"}])
    keys.select.return_value.eq.return_value.execute.side_effect = RuntimeError("database error")
    with patch.object(daily_key_verifier, "get_db", return_value=db), \
         patch("core.security.secure_credential_store.RotatingFernet") as cipher, \
         patch.object(daily_key_verifier, "_ping", new_callable=AsyncMock, return_value=True), \
         patch.object(daily_key_verifier.asyncio, "sleep", new_callable=AsyncMock), \
         patch.dict("os.environ", {"SUPREMEAI_CREDENTIAL_ENC_KEY": "test-key"}):
        cipher.return_value.decrypt.return_value = b"key"
        assert await daily_key_verifier.sweep() is False
    keys.upsert.assert_not_called()


def test_daily_sweep_is_consolidated_and_installs_required_imports():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert not (root / ".github/workflows/daily-key-health.yml").exists()
    workflow = yaml.safe_load((root / ".github/workflows/ops-maintenance.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["daily-key-health-sweep"]
    assert "0 3 * * *" in job["if"]
    assert "inputs.run_all == true" in job["if"]
    steps = job["steps"]
    install = next(s["run"] for s in steps if s.get("name") == "Install pinned verifier dependencies")
    for package in ("pydantic-settings", "fastapi", "httpx", "supabase", "cryptography"):
        assert package in install
    assert any(s.get("run") == "python scripts/ops/daily_key_verifier.py" for s in steps)


@pytest.mark.asyncio
async def test_sweep_decrypts_rotated_old_key_without_expiring_token():
    from cryptography.fernet import Fernet
    from core.security.secure_credential_store import RotatingFernet

    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    token = Fernet(old_key.encode()).encrypt_at_time(b"long-lived-key", current_time=1).decode()
    db = MagicMock()
    table = db.client.table.return_value
    table.select.return_value.execute.return_value = Mock(data=[{"id": "k1", "user_id": "u1", "provider": "groq", "encrypted_key": token}])
    table.select.return_value.eq.return_value.execute.return_value = Mock(data=[{"provider": "groq", "status": "valid"}])
    with patch.object(daily_key_verifier, "get_db", return_value=db), \
         patch.object(daily_key_verifier, "_ping", new_callable=AsyncMock, return_value=True) as probe, \
         patch.object(daily_key_verifier.asyncio, "sleep", new_callable=AsyncMock), \
         patch.dict("os.environ", {"ENCRYPTION_KEYS": f"{new_key},{old_key}"}):
        assert await daily_key_verifier.sweep() is True
    probe.assert_awaited_once_with("groq", "long-lived-key")
    assert RotatingFernet([old_key]).decrypt(token.encode(), ttl=None) == b"long-lived-key"
