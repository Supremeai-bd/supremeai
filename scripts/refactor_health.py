import os
import shutil

core_dir = "backend/core"
target_dir = os.path.join(core_dir, "health")

files_to_move = [
    "health_monitor.py",
    "health_probes.py",
    "self_healer.py"
]

os.makedirs(target_dir, exist_ok=True)

# Important: do not create __init__.py prematurely, we will create it manually if needed, or let python handle it as namespace package if possible.
# Actually, it's safer to create it AFTER moving, but wait, the module name is just health_monitor, health_probes etc.
# Python 3.3+ supports namespace packages. So no __init__.py is strictly required unless we import the directory itself.

for filename in files_to_move:
    src = os.path.join(core_dir, filename)
    dst = os.path.join(target_dir, filename)
    if os.path.exists(src) and not os.path.islink(src):
        shutil.move(src, dst)
        module_name = filename[:-3]
        wrapper_content = f"""import warnings
warnings.warn("This import is deprecated. Please use core.health.{module_name}", DeprecationWarning)

from core.health.{module_name} import *  # noqa: F403
"""
        with open(src, "w", encoding="utf-8") as f:
            f.write(wrapper_content)
        print(f"Moved {filename} and created wrapper.")
    else:
        print(f"Skipped {filename}")
