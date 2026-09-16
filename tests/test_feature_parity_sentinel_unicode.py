"""ERR-M03 regression tests — feature_parity_sentinel survives legacy codepages.

বাংলা: Windows কনসোল legacy codepage (cp1252) ব্যবহার করলে সেন্টিনেলের emoji
status glyph (🔍 U+1F50D) encode করতে না পেরে UnicodeEncodeError দিয়ে মাঝপথে
ক্র্যাশ করত (ERR-M03)। `force_utf8_streams()` সব আউটপুট স্ট্রিমকে UTF-8 +
`errors="replace"`-এ রিকনফিগার করে; যেসব র‍্যাপারে `reconfigure` নেই বা OSError
দেয় সেগুলোকে নীরবে বাদ দেওয়া হয় (crash নয়)।
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from feature_parity_sentinel import force_utf8_streams  # noqa: E402


class TestForceUtf8Streams:
    def test_reconfigures_stdout_and_stderr_to_utf8_replace(self):
        fake_out, fake_err = MagicMock(), MagicMock()
        force_utf8_streams(stdout=fake_out, stderr=fake_err)
        fake_out.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        fake_err.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

    def test_stream_without_reconfigure_is_left_alone(self):
        # Real TextIOWrapper-style check: an io.StringIO has no reconfigure.
        plain = io.StringIO()
        # Must not raise.
        force_utf8_streams(stdout=plain, stderr=plain)

    def test_reconfigure_raising_oserror_does_not_crash(self):
        stubborn = MagicMock()
        stubborn.reconfigure.side_effect = OSError("console gone")
        force_utf8_streams(stdout=stubborn, stderr=stubborn)

    def test_real_stdout_reconfigured_in_place(self):
        # On CPython, sys.stdout.reconfigure mutates the live stream in place —
        # after the call the encoding must be UTF-8 (or the stream must not
        # support reconfigure at all; both are acceptable, neither crashes).
        force_utf8_streams()
        try:
            assert sys.stdout.encoding.lower() == "utf-8"
        except AttributeError:
            pass  # test runner replaced stdout with a non-reconfigurable stream
