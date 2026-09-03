import re
import sys
from pathlib import Path
from loguru import logger

def scan_for_hardcoded_configs():
    root = Path.cwd()
    
    # ── Rules ──
    # 1. No hardcoded production urls
    hardcoded_domains = [
        "supremeai-backend-v2.onrender.com",
        "supremeai-backend-v2.onrender.com",
        "supremeai-lac.vercel.app",
        "supremeai-studio.vercel.app",
        "supremeai-admin.web.app"
    ]
    
    # 2. No scattered os.getenv for canonical endpoints
    banned_getenv = [
        "FRONTEND_URL",
        "BACKEND_URL",
        "ADMIN_URL",
        "APP_BASE_URL",
        "SUPABASE_URL",
        "DATABASE_URL"
    ]

    failed = False
    
    # Paths to ignore
    ignore_paths = { Path(p) for p in [
        ".git",
        ".kilo",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "dist",
        "dist-user",
        "dist-admin",
        "build",
        "scripts/advanced_analysis/hardcode_config_scanner.py", # Self-ignore
        "scripts/archive",
        "tests",
        "test_",
        ".test.",
        ".github"
    ] }

    for p in root.rglob("*"):
        if p.is_dir() or not p.is_file():
            continue
            
        # Check ignores by seeing if any ignored path is a parent of this path
        # or if the path string contains a substring for string-based ignores
        rel_parts = p.relative_to(root).parts
        if any(ignored in rel_parts for ignored in [".git", ".kilo", "node_modules", "venv", ".venv", "__pycache__", "dist", "dist-user", "dist-admin", "build", "archive", "tests", ".github", "deploy"]):
            continue
        if any(x in p.name for x in ["test_", ".test."]):
            continue
        if p.name == "hardcode_config_scanner.py":
            continue
            
        if p.suffix not in ['.py', '.ts', '.tsx', '.js', '.jsx', '.sh', '.json', '.yml', '.yaml']:
            continue
            
        try:
            content = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
            
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            # Check domains
            for domain in hardcoded_domains:
                if domain in line and 'config_validation' not in p.name and 'roadmap' not in p.name.lower():
                    # We are in checking logic - allow README and Roadmap
                    if p.suffix == '.md':
                        continue
                    # Log the exact location
                    logger.error(f"❌ Hardcoded domain '{domain}' found in {p.relative_to(root)}:{idx+1}")
                    logger.error(f"   > {line.strip()}")
                    failed = True
            
            # Check os.getenv
            if p.suffix == '.py' and 'core/config_fields.py' not in str(p) and 'core/config_validation.py' not in str(p) and 'settings.py' not in str(p):
                for var in banned_getenv:
                    if re.search(rf'os\.getenv\([\s\'"]*{var}[\s\'"]*', line):
                        logger.error(f"❌ Scattered os.getenv('{var}') found in {p.relative_to(root)}:{idx+1}")
                        logger.error(f"   > Please import `settings` from core.config instead.")
                        logger.error(f"   > {line.strip()}")
                        failed = True

    if failed:
        logger.error("🚨 Configuration scanner found hardcoded values. Please move these to Infisical/environment variables.")
        sys.exit(1)
    else:
        logger.success("✅ Zero-hardcode configuration verified.")

if __name__ == "__main__":
    scan_for_hardcoded_configs()
