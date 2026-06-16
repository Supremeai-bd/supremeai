from __future__ import annotations

import base64
import os
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - optional hardening
    CRYPTO_AVAILABLE = False


def generate_key() -> str:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography package is required for key generation")
    return Fernet.generate_key().decode()


class SecureCredentialStore:
    def __init__(self, encryption_key: Optional[str] = None) -> None:
        self.enabled = False
        self.fernet: Optional[Fernet] = None
        if CRYPTO_AVAILABLE:
            raw_key = encryption_key or os.getenv("SUPREMEAI_CREDENTIAL_ENC_KEY", "")
            if raw_key:
                try:
                    self.fernet = Fernet(raw_key.encode())
                    self.enabled = True
                except Exception as exc:
                    logger.warning(f"Invalid credential encryption key: {exc}")
        if not self.enabled:
            logger.warning("Credential encryption is disabled. Credentials will be stored as plaintext.")

    def encrypt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled or self.fernet is None:
            return payload
        try:
            data = base64.b64encode(__import__("json").dumps(payload, default=str).encode()).decode()
            token = self.fernet.encrypt(data.encode()).decode()
            return {"__enc__": True, "payload": token}
        except Exception as exc:
            logger.error(f"Credential encryption failed: {exc}")
            return payload

    def decrypt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled or self.fernet is None:
            return payload
        if not payload.get("__enc__"):
            return payload
        try:
            token = payload.get("payload", "")
            data = self.fernet.decrypt(token.encode()).decode()
            return __import__("json").loads(base64.b64decode(data).decode())
        except Exception as exc:
            logger.error(f"Credential decryption failed: {exc}")
            return payload

    def mask(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        masked = dict(payload)
        for field in ("password", "secret", "token"):
            if field in masked and masked[field]:
                masked[field] = "***masked***"
        return masked
