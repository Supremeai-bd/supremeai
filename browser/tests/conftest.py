import sys
from pathlib import Path
_br = Path(__file__).resolve().parent.parent
if str(_br) not in sys.path:
    sys.path.insert(0, str(_br))
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Self-alias so rowser.* imports resolve to satellite root
import types
if 'browser' not in sys.modules:
    browser_mod = types.ModuleType('browser')
    browser_mod.__path__ = [str(REPO_ROOT)]
    sys.modules['browser'] = browser_mod

