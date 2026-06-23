import re
import sys
from pathlib import Path

def parse_config_py(file_path: Path) -> set[str]:
    """Extract setting names from config.py Settings class."""
    if not file_path.exists():
        print(f"Error: Config file not found at {file_path}")
        sys.exit(1)
        
    content = file_path.read_text(encoding="utf-8")
    
    # Locate Settings class
    class_match = re.search(r"class Settings\(BaseSettings\):(.*?)(\n\n\w|\Z)", content, re.DOTALL)
    if not class_match:
        print("Error: Could not find Settings class in config.py")
        sys.exit(1)
        
    class_body = class_match.group(1)
    
    # Extract variables defined directly under the class body (exactly 4 spaces indentation)
    settings_vars = set()
    for line in class_body.splitlines():
        # Match lines starting with exactly 4 spaces, followed by a valid variable name, and then ':' or '='
        match = re.match(r"^ {4}([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::|=)", line)
        if match:
            var_name = match.group(1)
            # Skip Pydantic model_config or methods
            if var_name not in {"model_config"}:
                settings_vars.add(var_name.upper())
                
    return settings_vars

def parse_env_example(file_path: Path) -> set[str]:
    """Extract variable names from .env.example."""
    if not file_path.exists():
        print(f"Error: .env.example not found at {file_path}")
        sys.exit(1)
        
    content = file_path.read_text(encoding="utf-8")
    env_vars = set()
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Match "KEY=value" or "KEY="
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=", line)
        if match:
            env_vars.add(match.group(1).upper())
            
    return env_vars

def run_audit():
    project_root = Path(__file__).parent.parent
    config_path = project_root / "backend" / "core" / "config.py"
    env_example_path = project_root / ".env.example"
    
    print("[*] Auditing Configuration Settings...")
    config_keys = parse_config_py(config_path)
    env_keys = parse_env_example(env_example_path)
    
    # Ignore internal/local Pydantic configurations or those that don't belong in .env
    ignored_keys = {
        "PROJECT_NAME", "API_V1_STR", "APP_NAME", "CLAUDE_OPENROUTER_MODEL",
        "ADMIN_RULES_DB", "MEMORY_DB_DIR", "SKILL_REGISTRY_PATH"
    }
    
    missing_in_env = (config_keys - env_keys) - ignored_keys
    
    if missing_in_env:
        print("\n[!] CONFIG AUDIT FAILED!")
        print("The following keys are defined in backend/core/config.py but missing in .env.example:")
        for key in sorted(missing_in_env):
            print(f"  - {key}")
        print("\nAction Required: Please document these environment variables in .env.example.")
        sys.exit(1)
        
    print("[x] Configuration audit passed! All Pydantic Settings are aligned with .env.example.")
    sys.exit(0)

if __name__ == "__main__":
    run_audit()
