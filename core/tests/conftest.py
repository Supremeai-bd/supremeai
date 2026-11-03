import sys
from pathlib import Path
_core = Path(__file__).resolve().parent.parent
if str(_core) not in sys.path:
    sys.path.insert(0, str(_core))


