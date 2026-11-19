# Deprecated: moved to backend/core/plugins/experimental/slack_plugin.py

from ..experimental.slack_plugin import SlackPlugin as _SlackPlugin


class SlackPlugin(_SlackPlugin):
    """Shim — delegates to experimental implementation."""

    pass
