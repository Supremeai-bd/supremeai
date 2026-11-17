"""Model package bootstrap (dual-namespace bridge).

This project reaches the same model modules through two names: legacy code uses
``from models.<module> import ...`` (140 call sites) while newer code uses
``core.models.<module>``. Both must resolve to the SAME module object, so this
package registers itself and every submodule under both names in ``sys.modules``.

Import failures are LOGGED, never swallowed. They used to be dropped silently,
which made a broken model module disappear without a trace and surfaced much
later as a misleading ``ImportError: cannot import name 'X' from 'models'``.
"""

import importlib as _importlib
import logging as _logging
import sys as _sys
from pathlib import Path as _Path

_logger = _logging.getLogger(__name__)

for _alias in ("models", "core.models"):
    _sys.modules.setdefault(_alias, _sys.modules[__name__])

for _mod_file in sorted(_Path(__file__).resolve().parent.glob("*.py")):
    if _mod_file.stem == "__init__":
        continue
    try:
        _mod = _importlib.import_module(f"core.models.{_mod_file.stem}")
    except Exception as _exc:
        _logger.warning(
            "core.models submodule failed to import: %s (%s: %s)",
            _mod_file.stem,
            type(_exc).__name__,
            _exc,
        )
        continue
    _sys.modules.setdefault(f"models.{_mod_file.stem}", _mod)
    _sys.modules.setdefault(f"core.models.{_mod_file.stem}", _mod)


