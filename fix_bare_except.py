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
    
    # regex for bare except with a pass inside
    # can be `except:\n    pass` or `except Exception:\n    pass`
    # wait, the validator only complains about `except: pass` or `except:\n  pass`
    
    # We will replace `except:\n        pass` with `except Exception as e:\n        import logging\n        logging.getLogger(__name__).exception(f"Silenced error: {e}")`
    
    # The regex needs to handle the indentation
    
    def replacer(match):
        indent = match.group(1)
        return f"except Exception as e:\n{indent}    import logging\n{indent}    logging.getLogger(__name__).exception(f\"Silenced error: {{e}}\")"

    new_content = re.sub(r'except\s*:\n(\s+)pass', replacer, content)
    
    # Also handle `except Exception:\n    pass` just in case, though the rule is bare-except-pass
    def replacer2(match):
        indent = match.group(1)
        return f"except Exception as e:\n{indent}    import logging\n{indent}    logging.getLogger(__name__).exception(f\"Silenced error: {{e}}\")"
        
    new_content = re.sub(r'except Exception\s*:\n(\s+)pass', replacer2, new_content)
    
    # Handle single line `except: pass`
    new_content = re.sub(r'except\s*:\s*pass', 'except Exception as e: import logging; logging.getLogger(__name__).exception(f"Silenced error: {e}")', new_content)
    
    if content != new_content:
        path.write_text(new_content, encoding="utf-8")
        print(f"Fixed {path}")
    else:
        print(f"No changes for {path}")
