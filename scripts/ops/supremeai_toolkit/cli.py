"""Compatibility forwarding wrapper for scripts/supremeai_toolkit/cli.py.

Canonical SSOT: scripts/supremeai_toolkit/cli.py
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.supremeai_toolkit.cli import *

if __name__ == "__main__":
    from scripts.supremeai_toolkit.cli import main
    main()
