# Deprecated: moved to backend/core/plugins/experimental/telegram_plugin.py

from ..experimental.telegram_plugin import TelegramPlugin as _TelegramPlugin


class TelegramPlugin(_TelegramPlugin):
    """Shim — delegates to experimental implementation."""

    pass
