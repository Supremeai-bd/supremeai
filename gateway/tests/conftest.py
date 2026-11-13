import sys
from pathlib import Path

_gw = Path(__file__).resolve().parent.parent
_repo = _gw.parent
_core = _repo / "core"
# Core owns the flat api/models/agents namespaces. Gateway's legacy service
# imports still need its directory, but it must never shadow those namespaces.
for _p in (_gw, _repo, _core):
    if str(_p) in sys.path:
        sys.path.remove(str(_p))
    sys.path.insert(0, str(_p))



