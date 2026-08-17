import os
import shutil

core_dir = "backend/core"
security_dir = os.path.join(core_dir, "security")

files_to_move = [
    "auth_middleware.py",
    "api_key_middleware.py",
    "honeypot_middleware.py",
    "prompt_firewall.py",
    "input_sanitizer.py",
    "rbac.py",
    "secret_vault.py",
    "security_vault.py",
    "secure_credential_store.py",
    "origin_validator.py"
]

os.makedirs(security_dir, exist_ok=True)

for filename in files_to_move:
    src = os.path.join(core_dir, filename)
    dst = os.path.join(security_dir, filename)
    if os.path.exists(src) and not os.path.islink(src):
        # Move the file
        shutil.move(src, dst)

        # Create thin wrapper
        module_name = filename[:-3]
        wrapper_content = f"""import warnings
warnings.warn("This import is deprecated. Please use core.security.{module_name}", DeprecationWarning)

from core.security.{module_name} import *  # noqa: F403
"""
        with open(src, "w", encoding="utf-8") as f:
            f.write(wrapper_content)
        print(f"Moved {filename} and created wrapper.")
    else:
        print(f"Skipped {filename}")
