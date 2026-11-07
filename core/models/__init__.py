import importlib as _importlib
import sys as _sys
from pathlib import Path as _Path

for _alias in ("models", "core.models"):
    _sys.modules.setdefault(_alias, _sys.modules[__name__])

for _mod_file in sorted(_Path(__file__).resolve().parent.glob("*.py")):
    if _mod_file.stem == "__init__":
        continue
    try:
        _mod = _importlib.import_module(f"core.models.{_mod_file.stem}")
        _sys.modules.setdefault(f"models.{_mod_file.stem}", _mod)
        _sys.modules.setdefault(f"core.models.{_mod_file.stem}", _mod)
    except Exception:
        pass


