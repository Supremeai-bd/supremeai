"""SupremeAI Native Admin Authentication Module (Zero-Firebase).

Re-exports from gateway.service.admin_auth for backward compatibility with root gateway consumers.
"""

from __future__ import annotations

try:
    from gateway.service.admin_auth import *
    from gateway.service.admin_auth import (
        DEFAULT_ADMIN_EMAIL,
        DEFAULT_ADMIN_UID,
        DEFAULT_TRUSTED_BROWSER_DAYS,
        PRIMARY_OWNER_EMAIL,
        TRUSTED_BROWSER_COOKIE,
        build_provisioning_uri,
        check_totp,
        generate_totp_secret,
        issue_admin_jwt,
        issue_trusted_browser_token,
        router,
        verify_admin_jwt,
        verify_trusted_browser_token,
    )
except ImportError:
    from service.admin_auth import *
