"""
SupremeAI 2.0 — API Key Security Utilities
"""
import secrets
import string
import hashlib
import base64
from typing import Tuple
import bcrypt


# Configuration
KEY_PREFIX = "sk"
ENV_LIVE = "live"
ENV_TEST = "test"
ENV_DEV = "dev"
KEY_RANDOM_LENGTH = 32
CHECKSUM_LENGTH = 4


def generate_api_key(env: str = ENV_LIVE) -> Tuple[str, str]:
    """
    Generate a new API key and its prefix.

    Format: sk_<env>_<prefix>_<random>_<checksum>
    Example: sk_live_abc123de_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx_xxxx

    Returns:
        Tuple of (full_key, prefix)
    """
    # Generate random component
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(KEY_RANDOM_LENGTH))

    # Generate prefix (first 8 chars of a UUID-like random string)
    prefix_raw = secrets.token_hex(4)  # 8 hex chars

    # Build the key
    prefix = f"{KEY_PREFIX}_{env}_{prefix_raw}"

    # Generate checksum for tamper detection
    checksum_input = f"{prefix}_{random_part}"
    checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:CHECKSUM_LENGTH]

    full_key = f"{prefix}_{random_part}_{checksum}"

    return full_key, prefix


def hash_api_key(full_key: str) -> str:
    """
    Hash an API key using bcrypt for secure storage.

    Args:
        full_key: The complete API key string

    Returns:
        bcrypt hash string
    """
    # Use bcrypt with cost factor 12 (balanced between security and speed)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(full_key.encode('utf-8'), salt).decode('utf-8')


def verify_api_key(full_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its stored hash.

    Args:
        full_key: The API key to verify
        hashed_key: The stored bcrypt hash

    Returns:
        True if key matches, False otherwise
    """
    try:
        return bcrypt.checkpw(full_key.encode('utf-8'), hashed_key.encode('utf-8'))
    except Exception:
        return False


def validate_key_format(key: str) -> bool:
    """
    Validate the format of an API key.

    Checks:
    - Correct prefix format
    - Valid environment
    - Correct length
    - Valid checksum

    Args:
        key: The API key string to validate

    Returns:
        True if format is valid
    """
    parts = key.split('_')

    # Must have 5 parts: sk, env, prefix, random, checksum
    if len(parts) != 5:
        return False

    prefix, env, key_prefix, random_part, checksum = parts

    # Check prefix
    if prefix != KEY_PREFIX:
        return False

    # Check environment
    if env not in (ENV_LIVE, ENV_TEST, ENV_DEV):
        return False

    # Check lengths
    if len(key_prefix) != 8:
        return False
    if len(random_part) != KEY_RANDOM_LENGTH:
        return False
    if len(checksum) != CHECKSUM_LENGTH:
        return False

    # Verify checksum
    checksum_input = f"{prefix}_{env}_{key_prefix}_{random_part}"
    expected_checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:CHECKSUM_LENGTH]

    return checksum == expected_checksum


def extract_prefix_from_key(key: str) -> str:
    """
    Extract the searchable prefix from a full API key.

    Args:
        key: Full API key (sk_live_abc123de_xxxxxxxx..._xxxx)

    Returns:
        Prefix part (sk_live_abc123de)
    """
    parts = key.split('_')
    if len(parts) >= 3:
        return f"{parts[0]}_{parts[1]}_{parts[2]}"
    return key[:20]  # Fallback


def mask_key(key: str) -> str:
    """
    Mask an API key for display/logging (show only prefix + last 4).

    Args:
        key: Full API key

    Returns:
        Masked string like "sk_live_abc1...xxxx"
    """
    if len(key) <= 20:
        return key[:4] + "****"

    prefix = extract_prefix_from_key(key)
    return f"{prefix}...{key[-4:]}"


def generate_key_id() -> str:
    """Generate a unique key identifier for logging."""
    return secrets.token_urlsafe(16)


def is_safe_to_log(text: str) -> bool:
    """
    Check if text is safe to log (doesn't contain full API keys).

    Args:
        text: Text to check

    Returns:
        True if safe to log
    """
    # Simple heuristic: if text contains sk_ followed by long random string
    import re
    pattern = r'sk_(live|test|dev)_[a-zA-Z0-9]{8}_[a-zA-Z0-9]{32,}'
    return not bool(re.search(pattern, text))


def sanitize_for_logging(text: str) -> str:
    """
    Sanitize text by replacing API keys with masked versions.

    Args:
        text: Text that might contain API keys

    Returns:
        Sanitized text
    """
    import re
    pattern = r'(sk_(live|test|dev)_[a-zA-Z0-9]{8}_[a-zA-Z0-9]{32,}_[a-zA-Z0-9]{4})'

    def replacer(match):
        return mask_key(match.group(1))

    return re.sub(pattern, replacer, text)
