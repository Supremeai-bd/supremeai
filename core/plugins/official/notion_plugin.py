# Deprecated: moved to backend/core/plugins/experimental/notion_plugin.py

from ..experimental.notion_plugin import NotionPlugin as _NotionPlugin


class NotionPlugin(_NotionPlugin):
    """Shim — delegates to experimental implementation."""

    pass
