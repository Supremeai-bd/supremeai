import os
import re
from pathlib import Path

def replace_in_file(filepath, replacements):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content
        for old_str, new_str in replacements:
            new_content = new_content.replace(old_str, new_str)
            
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {filepath}")
    except Exception as e:
        print(f"Skipped {filepath}: {e}")

def fix_imports():
    backend_dir = Path("backend")
    replacements = [
        ("api.routes.config", "api.routes.config_routes"),
        ("backend.api.routes.config", "backend.api.routes.config_routes"),
        ("api.routes.llm_gateway", "api.routes.llm_gateway_routes"),
        ("core.api.routes.llm_gateway", "core.api.routes.llm_gateway_routes"),
        ("core.evolution.", "core.self_evolution."),
        ("core.evolution ", "core.self_evolution "),
        ("from core.evolution import", "from core.self_evolution import"),
        ("backend.core.evolution", "backend.core.self_evolution")
    ]
    
    for root, dirs, files in os.walk(backend_dir):
        # Prune dirs in-place
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'node_modules', '__pycache__')]
        for file in files:
            if file.endswith(".py"):
                replace_in_file(os.path.join(root, file), replacements)

def fix_bare_excepts():
    files_to_fix = [
        "backend/tests/conftest.py",
        "backend/tests/services/test_services_internet_monitor.py",
        "backend/tests/core/test_tier8.py",
        "backend/services/dynamic_ai/learning_engine.py",
        "backend/core/providers/n8n/adapter.py",
        "backend/core/observability/observability_middleware.py",
        "backend/core/zero_cost_architecture/zero_cost_patch_phase1_4.py",
        "backend/api/routes/websocket_agent.py"
    ]
    
    # We use regex to match both `except: pass` and `except Exception: pass`
    regex_bare = re.compile(r"except\s*:\s*\n\s*pass")
    regex_ex = re.compile(r"except\s+Exception\s*:\s*\n\s*pass")
    
    # Also handle single-line cases like `except: pass`
    regex_inline_bare = re.compile(r"except\s*:\s*pass")
    regex_inline_ex = re.compile(r"except\s+Exception\s*:\s*pass")
    
    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Determine indentation level and inject logger
        # For simplicity, we just inject import logging and use logging.warning
        if "import logging" not in content and "from loguru import logger" not in content:
            content = "import logging\n" + content
            
        new_content = re.sub(r"except\s*:\s*\n(\s*)pass", r"except Exception as e:\n\g<1>logging.warning(f'Ignored error: {e}')", content)
        new_content = re.sub(r"except\s+Exception\s*:\s*\n(\s*)pass", r"except Exception as e:\n\g<1>logging.warning(f'Ignored error: {e}')", new_content)
        
        new_content = re.sub(r"except\s*:\s*pass", r"except Exception as e: logging.warning(f'Ignored error: {e}')", new_content)
        new_content = re.sub(r"except\s+Exception\s*:\s*pass", r"except Exception as e: logging.warning(f'Ignored error: {e}')", new_content)

        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Fixed bare excepts in {file_path}")

if __name__ == "__main__":
    fix_imports()
    fix_bare_excepts()
