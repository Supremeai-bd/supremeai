import os

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import pytest
from unittest.mock import patch, MagicMock


class TestSecureCredentialStoreDisable:
    def test_plaintext_when_no_key(self):
        from core.secure_credential_store import SecureCredentialStore
        store = SecureCredentialStore()
        assert store.enabled is False
        data = {"password": "secret"}
        assert store.encrypt(data) == data
        assert store.decrypt(data) == data

    def test_mask_redacts_sensitive_fields(self):
        from core.secure_credential_store import SecureCredentialStore
        store = SecureCredentialStore()
        masked = store.mask({"username": "u", "password": "s", "token": "t", "other": "v"})
        assert masked["password"] == "***masked***"
        assert masked["token"] == "***masked***"
        assert masked["username"] == "u"

    def test_mask_no_sensitive_fields(self):
        from core.secure_credential_store import SecureCredentialStore
        store = SecureCredentialStore()
        masked = store.mask({"name": "safe"})
        assert masked["name"] == "safe"


@pytest.mark.skipif(
    __import__("core.secure_credential_store", fromlist=["CRYPTO_AVAILABLE"]).CRYPTO_AVAILABLE is False,
    reason="cryptography not installed"
)
class TestSecureCredentialStoreEncrypted:
    def test_encrypt_decrypt_roundtrip(self):
        from core.secure_credential_store import SecureCredentialStore, generate_key
        key = generate_key()
        store = SecureCredentialStore(key)
        assert store.enabled is True
        data = {"api_key": "abc123", "url": "https://api.example.com"}
        enc = store.encrypt(data)
        assert enc.get("__enc__") is True
        assert "payload" in enc
        dec = store.decrypt(enc)
        assert dec == data

    def test_decrypt_plaintext_passthrough(self):
        from core.secure_credential_store import SecureCredentialStore, generate_key
        key = generate_key()
        store = SecureCredentialStore(key)
        plain = {"user": "test"}
        assert store.decrypt(plain) == plain

    def test_encrypt_empty_payload(self):
        from core.secure_credential_store import SecureCredentialStore, generate_key
        key = generate_key()
        store = SecureCredentialStore(key)
        enc = store.encrypt({})
        dec = store.decrypt(enc)
        assert dec == {}
