"""API Key Management Database Access Layer (Gateway Re-export).

Re-exports from core.models.api_key to avoid duplicate code clones and maintain SSOT.
"""

from __future__ import annotations

from core.models.api_key import (
    create_api_key,
    delete_api_key,
    get_all_api_keys,
    get_api_key_by_hash,
    get_api_key_by_id,
    get_api_key_usage,
    get_api_key_usage_stats,
    get_api_keys_by_user,
    now_epoch,
    record_api_key_event,
    record_api_key_usage,
    revoke_api_key,
    rotate_api_key,
    update_api_key_last_used,
)

__all__ = [
    "create_api_key",
    "delete_api_key",
    "get_all_api_keys",
    "get_api_key_by_hash",
    "get_api_key_by_id",
    "get_api_key_usage",
    "get_api_key_usage_stats",
    "get_api_keys_by_user",
    "now_epoch",
    "record_api_key_event",
    "record_api_key_usage",
    "revoke_api_key",
    "rotate_api_key",
    "update_api_key_last_used",
]
