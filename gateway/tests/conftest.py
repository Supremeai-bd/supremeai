import sys
from pathlib import Path
_gw = Path(__file__).resolve().parent.parent
if str(_gw) not in sys.path:
    sys.path.insert(0, str(_gw))


