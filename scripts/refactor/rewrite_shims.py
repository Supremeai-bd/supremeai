"""backend arch refactor — shim গুলো lazy (PEP 562) ফর্ম্যাটে রিজেনারেট করে।

সমস্যা: eager shim (`from backend.<new> import *`) `backend/core/__init__.py`
initialize-এর সময় রিয়েল মডিউল import করে circular import ঘটায়। lazy shim শুধু
অ্যাট্রিবিউট অ্যাক্সেসে (getattr) রিয়েল মডিউল import করে, তাই package init-এর সময়
লুপ হয় না।

ব্যবহার:
  python scripts/refactor/rewrite_shims.py
(সব moves_*.json থেকে old/new জোড়া নিয়ে শুধু shim ফাইল (old path) রিরাইট করে)
"""
import json
import glob
import warnings
from pathlib import Path

REPO = Path(r"F:\supremeai backup")


def lazy_shim(old_rel: str, new_dotted: str) -> str:
    name = Path(old_rel).stem
    return (
        f"# DEPRECATED: backend.core.{name} -> {new_dotted}\n"
        "# নোট: backend architecture refactor plan অনুযায়ী সরানো হয়েছে।\n"
        "# ভবিষ্যতে সব importer নতুন path-এ সরিয়ে এই shim মুছে ফেলতে হবে।\n"
        "import importlib\n"
        "import warnings\n"
        "\n"
        f'_DEPRECATED_TARGET = "{new_dotted}"\n'
        "_warned = False\n"
        "\n"
        "def __getattr__(name):\n"
        "    global _warned\n"
        "    if not _warned:\n"
        "        warnings.warn(\n"
        f'            "backend.core.{name} is deprecated; import from {new_dotted}",\n'
        "            DeprecationWarning, stacklevel=2,\n"
        "        )\n"
        "        _warned = True\n"
        "    mod = importlib.import_module(_DEPRECATED_TARGET)\n"
        "    return getattr(mod, name)\n"
        "\n"
        "def __dir__():\n"
        "    return list(importlib.import_module(_DEPRECATED_TARGET).__dict__.keys())\n"
    )


def main() -> None:
    moves = []
    for f in sorted(glob.glob(str(REPO / "scripts/refactor/moves_*.json"))):
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        moves.extend(data)
    for old_rel, new_rel in moves:
        new_dotted = ".".join(Path(new_rel).with_suffix("").parts)
        old_path = REPO / old_rel
        if not old_path.exists():
            print(f"  ! skip (no shim file): {old_rel}")
            continue
        old_path.write_text(lazy_shim(old_rel, new_dotted), encoding="utf-8")
        print(f"  + lazy shim: {old_rel} -> {new_dotted}")
    print("DONE")


if __name__ == "__main__":
    main()
