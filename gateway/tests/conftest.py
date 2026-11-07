import sys
from pathlib import Path

_gw = Path(__file__).resolve().parent.parent
_repo = _gw.parent
_core = _repo / "core"
for _p in (_core, _gw, _repo):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))



