# Deprecated: moved to backend/core/plugins/experimental/google_drive_plugin.py

from ..experimental.google_drive_plugin import GoogleDrivePlugin as _GoogleDrivePlugin


class GoogleDrivePlugin(_GoogleDrivePlugin):
    """Shim — delegates to experimental implementation."""

    pass
