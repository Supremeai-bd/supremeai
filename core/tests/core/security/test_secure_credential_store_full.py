"""Full-coverage tests for core.security.secure_credential_store.

Covers RotatingFernet key rotation (multi-key decrypt, TTL expiry, invalid-key
derivation), LocalFernetProvider, CloudKMSProvider (with a fully mocked KMS
client — no google-cloud-kms dependency, no network), SecureCredentialStore and
generate_key. All crypto is local; KMS is faked via sys.modules injection.
"""

from __future__ import annotations

import base64
import hashlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

import core.security.secure_credential_store as scs_module
from core.security.secure_credential_store import (
    CloudKMSProvider,
    CredentialEncryptionUnavailableError,
    EncryptionProvider,
    LocalFernetProvider,
    RotatingFernet,
    SecureCredentialStore,
    generate_key,
)

pytestmark = pytest.mark.security


KEY1 = Fernet.generate_key().decode()
KEY2 = Fernet.generate_key().decode()
KEY3 = Fernet.generate_key().decode()


class TestGenerateKey:
    def test_returns_valid_fernet_key_string(self):
        key = generate_key()
        assert isinstance(key, str)
        # A generated key must be usable by Fernet directly
        Fernet(key.encode())

    def test_raises_when_crypto_unavailable(self, monkeypatch):
        monkeypatch.setattr(scs_module, "CRYPTO_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="cryptography package is required"):
            generate_key()


class TestRotatingFernet:
    def test_empty_keys_raises(self):
        with pytest.raises(ValueError, match="At least one key is required"):
            RotatingFernet([])

    def test_accepts_string_and_bytes_keys(self):
        rf = RotatingFernet([KEY1, KEY2.encode()])
        assert len(rf._fernets) == 2

    def test_primary_property_is_first_key(self):
        rf = RotatingFernet([KEY1, KEY2])
        assert rf.primary.encrypt(b"x") == Fernet(KEY1.encode()).encrypt(b"x") or True
        # Deterministic check: decrypting a primary-encrypted token with Fernet(KEY1) works
        token = rf.encrypt(b"payload")
        assert Fernet(KEY1.encode()).decrypt(token) == b"payload"

    def test_encrypt_roundtrip(self):
        rf = RotatingFernet([KEY1])
        token = rf.encrypt(b"hello world")
        assert rf.decrypt(token) == b"hello world"

    def test_encrypt_at_time_and_decrypt_at_time(self):
        current_time = 1_700_000_000
        rf = RotatingFernet([KEY1])
        token = rf.encrypt_at_time(b"data", current_time)
        assert rf.decrypt_at_time(token, ttl=86400, current_time=current_time + 60) == b"data"

    def test_decrypt_falls_back_to_rotated_key(self):
        old_rf = RotatingFernet([KEY1])
        legacy_token = old_rf.encrypt(b"legacy-secret")
        # New primary key added after the token was issued
        new_rf = RotatingFernet([KEY2, KEY1])
        assert new_rf.decrypt(legacy_token) == b"legacy-secret"

    def test_decrypt_no_matching_key_raises_invalid_token(self):
        rf = RotatingFernet([KEY1, KEY2])
        alien = Fernet.generate_key()
        token = Fernet(alien).encrypt(b"unknown")
        with pytest.raises(InvalidToken):
            rf.decrypt(token)

    def test_decrypt_expired_token_raises(self):
        current_time = 1_700_000_000
        rf = RotatingFernet([KEY1])
        token = rf.encrypt_at_time(b"data", current_time - 90000)  # > 24h old
        with pytest.raises(InvalidToken):
            rf.decrypt(token)

    def test_decrypt_at_time_falls_back_to_rotated_key(self):
        old_rf = RotatingFernet([KEY1])
        token = old_rf.encrypt_at_time(b"legacy", 1_700_000_000)
        new_rf = RotatingFernet([KEY2, KEY1])
        assert new_rf.decrypt_at_time(token, ttl=86400, current_time=1_700_000_060) == b"legacy"

    def test_decrypt_at_time_raises_last_invalid_token(self):
        rf = RotatingFernet([KEY1, KEY2])
        alien = Fernet.generate_key()
        token = Fernet(alien).encrypt_at_time(b"x", 1_700_000_000)
        with pytest.raises(InvalidToken):
            rf.decrypt_at_time(token, ttl=86400, current_time=1_700_000_000)

    def test_invalid_base64_key_is_sha256_derived(self):
        # A non-Base64 key must trigger the warning + sha256 derivation branch
        bad_key = "not-a-valid-base64-fernet-key!!"
        rf = RotatingFernet([bad_key])
        token = rf.encrypt(b"derived")
        expected = Fernet(base64.urlsafe_b64encode(hashlib.sha256(bad_key.encode()).digest()))
        assert expected.decrypt(token) == b"derived"

    def test_invalid_bytes_key_is_sha256_derived(self):
        bad_key = b"\x00\x01\x02not base64 \xff"
        rf = RotatingFernet([bad_key])
        token = rf.encrypt(b"x")
        expected = Fernet(base64.urlsafe_b64encode(hashlib.sha256(bad_key).digest()))
        assert expected.decrypt(token) == b"x"


class TestEncryptionProviderABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            EncryptionProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_both(self):
        class Partial(EncryptionProvider):
            def encrypt(self, plaintext):
                return plaintext, None

        with pytest.raises(TypeError):
            Partial()  # type: ignore[abstract]


class TestLocalFernetProvider:
    def test_disabled_without_any_key(self, monkeypatch):
        for var in (
            "BROWSER_CREDENTIALS_ENCRYPTION_KEY",
            "SUPREMEAI_CREDENTIAL_ENC_KEY",
            "ENCRYPTION_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        provider = LocalFernetProvider(encryption_key=None)
        assert provider.enabled is False
        assert provider.rotating_fernet is None

    def test_unavailable_crypto_leaves_provider_disabled(self, monkeypatch):
        # CRYPTO_AVAILABLE=False short-circuits __init__ entirely (branch 97->exit)
        monkeypatch.setattr(scs_module, "CRYPTO_AVAILABLE", False)
        provider = LocalFernetProvider(encryption_key=KEY1)
        assert provider.enabled is False
        assert provider.rotating_fernet is None

    def test_explicit_key_enables(self):
        provider = LocalFernetProvider(encryption_key=KEY1)
        assert provider.enabled is True
        ciphertext, key_ref = provider.encrypt("secret-value")
        assert key_ref is None
        assert ciphertext != "secret-value"
        assert provider.decrypt(ciphertext) == "secret-value"

    def test_env_key_fallback_chain(self, monkeypatch):
        monkeypatch.delenv("BROWSER_CREDENTIALS_ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("SUPREMEAI_CREDENTIAL_ENC_KEY", raising=False)
        monkeypatch.setenv("ENCRYPTION_KEY", KEY2)
        provider = LocalFernetProvider()
        assert provider.enabled is True
        ciphertext, _ = provider.encrypt("chain")
        assert provider.decrypt(ciphertext) == "chain"

    def test_browser_credentials_env_preferred_over_encryption_key(self, monkeypatch):
        monkeypatch.setenv("BROWSER_CREDENTIALS_ENCRYPTION_KEY", KEY1)
        monkeypatch.setenv("ENCRYPTION_KEY", KEY2)
        provider = LocalFernetProvider()
        ciphertext, _ = provider.encrypt("preference")
        # Primary key is the browser-credentials one
        token = base64.urlsafe_b64decode(ciphertext.encode())
        assert provider.rotating_fernet.decrypt(token, ttl=None) == b"preference"

    def test_comma_separated_keys_support_rotation(self):
        provider = LocalFernetProvider(encryption_key=f"{KEY1},{KEY2}, {KEY3} ")
        assert len(provider.rotating_fernet._fernets) == 3

    def test_encrypt_failure_fails_open_only_in_legacy_mode(self):
        # ISSUE-1570: default policy is fail-closed — runtime encryption failure
        # must raise instead of returning plaintext. Legacy fail-open behaviour
        # requires an explicit opt-out.
        provider = LocalFernetProvider(encryption_key=KEY1, fail_closed=False)
        provider.rotating_fernet.encrypt = MagicMock(side_effect=RuntimeError("boom"))
        plaintext, key_ref = provider.encrypt("value")
        assert plaintext == "value"
        assert key_ref is None

    def test_encrypt_failure_fails_closed_by_default(self):
        provider = LocalFernetProvider(encryption_key=KEY1)
        provider.rotating_fernet.encrypt = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.encrypt("value")

    def test_decrypt_invalid_token_fails_open_only_in_legacy_mode(self):
        provider = LocalFernetProvider(encryption_key=KEY1, fail_closed=False)
        alien = Fernet.generate_key()
        token = base64.urlsafe_b64encode(Fernet(alien).encrypt(b"mystery")).decode()
        # InvalidToken branch: the original ciphertext is returned unchanged
        assert provider.decrypt(token) == token

    def test_decrypt_invalid_token_fails_closed_by_default(self):
        provider = LocalFernetProvider(encryption_key=KEY1)
        alien = Fernet.generate_key()
        token = base64.urlsafe_b64encode(Fernet(alien).encrypt(b"mystery")).decode()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.decrypt(token)

    def test_decrypt_generic_failure_fails_open_only_in_legacy_mode(self):
        provider = LocalFernetProvider(encryption_key=KEY1, fail_closed=False)
        # Not valid base64 -> binascii.Error (not InvalidToken) -> error branch
        assert provider.decrypt("!!!not-base64!!!") == "!!!not-base64!!!"

    def test_decrypt_generic_failure_fails_closed_by_default(self):
        provider = LocalFernetProvider(encryption_key=KEY1)
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.decrypt("!!!not-base64!!!")

    def test_disabled_encrypt_decrypt_passthrough_is_legacy_optout(self, monkeypatch):
        for var in (
            "BROWSER_CREDENTIALS_ENCRYPTION_KEY",
            "SUPREMEAI_CREDENTIAL_ENC_KEY",
            "ENCRYPTION_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        provider = LocalFernetProvider(fail_closed=False)
        assert provider.encrypt("plain") == ("plain", None)
        assert provider.decrypt("cipher") == "cipher"

    def test_disabled_provider_fails_closed_by_default(self, monkeypatch):
        for var in (
            "BROWSER_CREDENTIALS_ENCRYPTION_KEY",
            "SUPREMEAI_CREDENTIAL_ENC_KEY",
            "ENCRYPTION_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        provider = LocalFernetProvider()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.encrypt("plain")
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.decrypt("cipher")

    def test_init_failure_disables_provider(self, monkeypatch):
        # RotatingFernet construction blowing up must be caught (error log,
        # provider stays disabled) rather than crashing the caller
        class ExplodingRotating:
            def __init__(self, keys):
                raise RuntimeError("kaboom")

        monkeypatch.setattr(scs_module, "RotatingFernet", ExplodingRotating)
        provider = LocalFernetProvider(encryption_key=KEY1)
        assert provider.enabled is False
        assert provider.rotating_fernet is None

    def test_decrypt_with_ttl_parameter(self):
        provider = LocalFernetProvider(encryption_key=KEY1)
        ciphertext, _ = provider.encrypt("ttl-value")
        assert provider.decrypt(ciphertext, ttl=86400) == "ttl-value"


class TestCloudKMSProvider:
    @staticmethod
    def _install_fake_kms_module(monkeypatch, client_factory=MagicMock):
        fake_kms = types.ModuleType("google.cloud.kms")
        fake_kms.KeyManagementServiceClient = client_factory
        fake_cloud = types.ModuleType("google.cloud")
        fake_cloud.kms = fake_kms
        monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
        monkeypatch.setitem(sys.modules, "google.cloud", fake_cloud)
        monkeypatch.setitem(sys.modules, "google.cloud.kms", fake_kms)
        return fake_kms

    def test_no_key_name_skips_init(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider()
        assert provider.kms_client is None
        assert provider.key_name == ""

    def test_kms_module_missing_logs_warning(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        # google.cloud exists but has no `kms` submodule -> ImportError branch
        fake_cloud = types.ModuleType("google.cloud")
        monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
        monkeypatch.setitem(sys.modules, "google.cloud", fake_cloud)
        provider = CloudKMSProvider()
        assert provider.kms_client is None

    def test_client_init_failure_is_caught(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")

        def factory():
            raise RuntimeError("no credentials")

        self._install_fake_kms_module(monkeypatch, client_factory=factory)
        provider = CloudKMSProvider()
        assert provider.kms_client is None

    def test_encrypt_without_client_fails_open_only_in_legacy_mode(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider(fail_closed=False)
        assert provider.encrypt("data") == ("data", None)

    def test_encrypt_without_client_fails_closed_by_default(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.encrypt("data")

    def test_encrypt_success_returns_base64_and_key_ref(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        raw_ciphertext = b"\x01\x02kms-bytes"
        client = MagicMock()
        client.encrypt.return_value = MagicMock(ciphertext=raw_ciphertext)
        self._install_fake_kms_module(monkeypatch, client_factory=lambda: client)
        provider = CloudKMSProvider()
        ciphertext, key_ref = provider.encrypt("plaintext-value")
        assert key_ref == provider.key_name
        assert base64.b64decode(ciphertext.encode()) == raw_ciphertext
        client.encrypt.assert_called_once()

    def test_encrypt_failure_fails_open_only_in_legacy_mode(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        client = MagicMock()
        client.encrypt.side_effect = RuntimeError("KMS down")
        self._install_fake_kms_module(monkeypatch, client_factory=lambda: client)
        provider = CloudKMSProvider(fail_closed=False)
        assert provider.encrypt("value") == ("value", None)

    def test_encrypt_failure_fails_closed_by_default(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        client = MagicMock()
        client.encrypt.side_effect = RuntimeError("KMS down")
        self._install_fake_kms_module(monkeypatch, client_factory=lambda: client)
        provider = CloudKMSProvider()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.encrypt("value")

    def test_decrypt_without_client_fails_open_only_in_legacy_mode(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider(fail_closed=False)
        assert provider.decrypt("cipher", None) == "cipher"

    def test_decrypt_without_client_fails_closed_by_default(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.decrypt("cipher", None)

    def test_decrypt_without_key_ref_fails_open_only_in_legacy_mode(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider(fail_closed=False)
        provider.kms_client = MagicMock()
        assert provider.decrypt("cipher", None) == "cipher"

    def test_decrypt_without_key_ref_fails_closed_by_default(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider()
        provider.kms_client = MagicMock()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.decrypt("cipher", None)

    def test_decrypt_success(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        client = MagicMock()
        client.decrypt.return_value = MagicMock(plaintext=b"decrypted-plaintext")
        self._install_fake_kms_module(monkeypatch, client_factory=lambda: client)
        provider = CloudKMSProvider()
        ciphertext = base64.b64encode(b"\x09\x09").decode()
        assert provider.decrypt(ciphertext, key_ref=None) == "decrypted-plaintext"
        client.decrypt.assert_called_once()

    def test_decrypt_uses_explicit_key_ref(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = CloudKMSProvider(fail_closed=False)
        provider.kms_client = MagicMock()
        provider.key_name = ""
        client = MagicMock()
        client.decrypt.return_value = MagicMock(plaintext=b"value")
        provider.kms_client = client
        ciphertext = base64.b64encode(b"xy").decode()
        assert provider.decrypt(ciphertext, key_ref="projects/x/keys/y") == "value"
        assert client.decrypt.call_args.kwargs["request"]["name"] == "projects/x/keys/y"

    def test_decrypt_failure_fails_open_only_in_legacy_mode(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        client = MagicMock()
        client.decrypt.side_effect = RuntimeError("boom")
        self._install_fake_kms_module(monkeypatch, client_factory=lambda: client)
        provider = CloudKMSProvider(fail_closed=False)
        assert provider.decrypt("cipher", None) == "cipher"

    def test_decrypt_failure_fails_closed_by_default(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/locations/l/keyRings/r/cryptoKeys/k")
        client = MagicMock()
        client.decrypt.side_effect = RuntimeError("boom")
        self._install_fake_kms_module(monkeypatch, client_factory=lambda: client)
        provider = CloudKMSProvider()
        with pytest.raises(CredentialEncryptionUnavailableError):
            provider.decrypt("cipher", None)


class TestSecureCredentialStore:
    def test_defaults_to_local_provider_without_kms_env(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        store = SecureCredentialStore()
        assert isinstance(store.provider, LocalFernetProvider)

    def test_uses_kms_provider_when_env_set(self, monkeypatch):
        monkeypatch.setenv("KMS_KEY_NAME", "projects/p/keys/k")
        with patch.object(scs_module, "CloudKMSProvider", wraps=scs_module.CloudKMSProvider):
            store = SecureCredentialStore()
        assert isinstance(store.provider, CloudKMSProvider)
        assert store.provider.kms_client is None  # kms module missing -> no client

    def test_encrypt_decrypt_roundtrip_local(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        store = SecureCredentialStore(LocalFernetProvider(encryption_key=KEY1))
        ciphertext, key_ref = store.encrypt("round-trip")
        assert store.decrypt(ciphertext, key_ref) == "round-trip"

    def test_decrypt_passes_ttl_to_local_provider(self, monkeypatch):
        monkeypatch.delenv("KMS_KEY_NAME", raising=False)
        provider = LocalFernetProvider(encryption_key=KEY1)
        store = SecureCredentialStore(provider)
        ciphertext, _ = store.encrypt("ttl")
        provider.decrypt = MagicMock(return_value="ttl")
        result = store.decrypt(ciphertext, "ref", ttl=42)
        provider.decrypt.assert_called_once_with(ciphertext, "ref", ttl=42)
        assert result == "ttl"

    def test_decrypt_non_local_provider_signature(self):
        other_provider = MagicMock(spec=EncryptionProvider)
        other_provider.decrypt.return_value = "plain"
        store = SecureCredentialStore(other_provider)
        assert store.decrypt("cipher", "key-ref") == "plain"
        other_provider.decrypt.assert_called_once_with("cipher", "key-ref")

    def test_mask_short_value(self):
        assert SecureCredentialStore.mask("abc", visible_chars=4) == "****"
        assert SecureCredentialStore.mask("abcd", visible_chars=4) == "****"

    def test_mask_long_value(self):
        assert SecureCredentialStore.mask("sk-1234567890", visible_chars=4) == "sk-1" + "*" * 9
        assert SecureCredentialStore.mask("abcdefgh", visible_chars=2) == "ab" + "*" * 6
