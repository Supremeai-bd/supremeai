import re
from pathlib import Path

files = [
    'scripts/health/check_system_health.py',
    'scripts/monitoring/capacity_planner.py',
    'scripts/monitoring/sla_tracker.py',
    'scripts/tenant/auto_tenant_setup.py'
]

for fn in files:
    p = Path(fn)
    if not p.exists(): continue
    c = p.read_text('utf-8')
    if 'from core.config import settings' not in c:
        injection = '''import sys\nfrom pathlib import Path\nsys.path.append(str(Path(__file__).parent.parent.parent / "backend"))\nfrom core.config import settings\n'''
        c = re.sub(r'(import os\n)', r'\1' + injection, c, count=1)
        
    c = re.sub(r'os\.getenv\([\s\'"]*BACKEND_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.backend_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*DATABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.database_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*APP_BASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.app_base_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*SUPABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.supabase_url', c)
    
    p.write_text(c, 'utf-8')
