import re
from pathlib import Path

files_to_fix = [
    "tests/services/test_services_internet_monitor.py",
    "tests/core/test_tier8.py",
    "services/dynamic_ai/learning_engine.py",
    "core/providers/n8n/adapter.py",
    "core/observability/observability_middleware.py",
    "core/zero_cost_architecture/zero_cost_patch_phase1_4.py",
]

base_dir = Path("f:/supremeai/backend")

for rel_path in files_to_fix:
    path = base_dir / rel_path
    if not path.exists():
        print(f"File not found: {path}")
        continue
        
    content = path.read_text(encoding="utf-8")
    
    # We match "except [something]:\n    pass" or "except:\n    pass"
    # and replace with "except [something]:\n    import logging\n    logging.getLogger(__name__).exception('Silenced error')"
    
    def replacer(match):
        except_clause = match.group(1)
        indent = match.group(2)
        # We don't have access to the exception variable if it doesn't have "as e", so we just print a generic message
        return f"{except_clause}:\n{indent}import logging\n{indent}logging.getLogger(__name__).warning('Silenced error in except-pass block')"

    new_content = re.sub(r'(except[^:]*):\n(\s+)pass', replacer, content)
    
    if content != new_content:
        path.write_text(new_content, encoding="utf-8")
        print(f"Fixed {path}")
    else:
        print(f"No changes for {path}")
