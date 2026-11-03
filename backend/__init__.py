import sys
import core

# Alias backend.* onto core.* so legacy "backend." imports keep working.
sys.modules["backend.core"] = core
try:
    import pkgutil
    for _m in pkgutil.iter_modules(core.__path__):
        _name = _m.name
        if _name == "core":
            continue
        try:
            _mod = __import__("core." + _name, fromlist=["*"])
            sys.modules["backend." + _name] = _mod
        except Exception:
            pass
except Exception:
    pass

# Allow attribute access backend.x -> core.x
import types as _types

class _BackendModule(_types.ModuleType):
    def __getattr__(self, name):
        return getattr(core, name)

sys.modules[__name__].__class__ = _BackendModule
