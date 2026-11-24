"""Deprecated duplicate of ``browser/session_manager.py`` — re-export shim.

Historically this file was a hand-maintained byte-identical copy of the
canonical top-level ``browser/session_manager.py`` (with only the logger
import differing). Two copies of the pool guaranteed drift — e.g. the Windows
-hardcoded automation profile and the sync Playwright factory inside async
callers were fixed in one path while the other stayed broken.

No module imports this copy (verified by repo-wide grep on 2026-11-24); it is
kept only to satisfy any external importers of the old path. Prefer
``browser.session_manager`` directly.
"""

from browser.session_manager import (  # noqa: F401
    ACTION_REGISTRY,
    AUTOMATION_BIND_ADDRESS,
    BrowserSessionManager,
    automation_profile_dir,
    chrome_launch_args,
    register_action,
    run_action_sequence,
)

__all__ = [
    "BrowserSessionManager",
    "chrome_launch_args",
    "automation_profile_dir",
    "AUTOMATION_BIND_ADDRESS",
    "register_action",
    "run_action_sequence",
    "ACTION_REGISTRY",
]
