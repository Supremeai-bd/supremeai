import os
import shutil

core_dir = "backend/core"
target_dir = os.path.join(core_dir, "llm")

files_to_move = [
    "llm_gateway.py",
    "token_budget.py",
    "token_deductor.py",
    "free_tier_tracker.py"
]

os.makedirs(target_dir, exist_ok=True)

for filename in files_to_move:
    src = os.path.join(core_dir, filename)
    dst = os.path.join(target_dir, filename)
    if os.path.exists(src) and not os.path.islink(src):
        shutil.move(src, dst)
        module_name = filename[:-3]
        wrapper_content = f"""import warnings
warnings.warn("This import is deprecated. Please use core.llm.{module_name}", DeprecationWarning)

from core.llm.{module_name} import *  # noqa: F403
"""
        with open(src, "w", encoding="utf-8") as f:
            f.write(wrapper_content)
        print(f"Moved {filename} and created wrapper.")
    else:
        print(f"Skipped {filename}")
