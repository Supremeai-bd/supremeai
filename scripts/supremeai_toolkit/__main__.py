# -*- coding: utf-8 -*-
"""`python -m supremeai_toolkit` entry — cli.main()-এ হাত দেয়।"""

# বাংলা মন্তব্য: scripts/ ডিরেক্টরিকে sys.path-এ যোগ করে প্যাকেজ-মোড রান নিশ্চিত করি।
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from supremeai_toolkit.cli import main
else:
    from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
