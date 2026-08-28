from pathlib import Path
import re

files = list(Path('scripts/ai').glob('*.py')) + \
        list(Path('scripts/billing').glob('*.py')) + \
        [Path('scripts/deploy/update_render.py')]

for p in files:
    if not p.exists(): continue
    c = p.read_text('utf-8')
    if 'from core.config import settings' not in c:
        # inject
        import_stmt = 'import sys\nfrom pathlib import Path\nsys.path.append(str(Path(__file__).resolve().parent.parent.parent / "backend"))\nfrom core.config import settings\n'
        # find first import
        m = re.search(r'^(import |from )', c, re.MULTILINE)
        if m:
            c = c[:m.start()] + import_stmt + c[m.start():]
            
    c = re.sub(r'os\.getenv\([\s\'"]*BACKEND_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.backend_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*DATABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.database_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*APP_BASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.app_base_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*SUPABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.supabase_url', c)
    
    p.write_text(c, 'utf-8')
