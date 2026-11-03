import importlib
import os
import sys

import pytest

# Set ENCRYPTION_KEY before importing core.security.security_vault to avoid import-time crash
os.environ.setdefault("ENCRYPTION_KEY", "9llmzMU2XSRhbAS-R__JMW1XLZzc0ll7obD_RqaVwno=")

# Reload in case module was partially imported
if "core.security.security_vault" in sys.modules:
    importlib.reload(sys.modules["core.security.security_vault"])

# Wave 3.9 (issue #1265): implementation folded into secure_credential_store;
# security_vault is a re-export shim. The _vault instance lives in the impl module.
from core.security import secure_credential_store, security_vault
from core.security.security_vault import decrypt_token, encrypt_token


def test_encrypt_token_returns_string():
    result = encrypt_token("my-secret")
    assert isinstance(result, str)
    assert result != ""


def test_decrypt_token_returns_plaintext():
    encrypted = encrypt_token("my-secret")
    result = decrypt_token(encrypted)
    assert result == "my-secret"


def test_encrypt_empty_plain_text():
    assert encrypt_token("") == ""


def test_decrypt_empty_cipher_text():
    assert decrypt_token("") == ""


def test_decrypt_invalid_token_raises_error():
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_token("invalid-token")


def test_encrypt_token_uses_fernet(monkeypatch):
    class MockFernet:
        def encrypt(self, data):
            assert data == b"hello"
            return b"encrypted-bytes"

    # বাংলা মন্তব্য: monkeypatch ব্যবহার করে security_vault.fernet mock করা হলো
    monkeypatch.setattr(secure_credential_store, "_vault", MockFernet())
    result = encrypt_token("hello")
    assert result == "encrypted-bytes"


def test_decrypt_token_handles_exception(monkeypatch):
    class MockFernet:
        def decrypt(self, data):
            raise Exception("Decryption failed")

    # বাংলা মন্তব্য: monkeypatch ব্যবহার করে security_vault.fernet mock করা হলো
    monkeypatch.setattr(secure_credential_store, "_vault", MockFernet())
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_token("invalid")
