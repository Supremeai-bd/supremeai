from pathlib import Path
import re

files = [
    'backend/core/config.py',
    'backend/core/db.py',
    'backend/database/storage_client.py',
    'backend/memory/cloud_postgres_store.py',
    'backend/memory/supabase_store.py',
    'backend/scripts/migrate_embeddings.py',
    'backend/services/memory_service.py',
    'backend/storage/asset_manager.py',
    'backend/tools/agent_tools.py',
    'backend/api/routes/service_topology.py'
]

for fn in files:
    p = Path(fn)
    if not p.exists(): continue
    c = p.read_text('utf-8')
    if 'from core.config import settings' not in c:
        # inject
        import_stmt = 'from core.config import settings\n'
        # find first import
        m = re.search(r'^(import |from )', c, re.MULTILINE)
        if m:
            c = c[:m.start()] + import_stmt + c[m.start():]
            
    c = re.sub(r'os\.getenv\([\s\'"]*BACKEND_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.backend_url', c)
    c = re.sub(r'os\.environ\.get\([\s\'"]*BACKEND_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.backend_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*DATABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.database_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*APP_BASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.app_base_url', c)
    c = re.sub(r'os\.getenv\([\s\'"]*SUPABASE_URL[\s\'"]*(?:,\s*[\'"].*?[\'"])?\)', 'settings.supabase_url', c)
    
    p.write_text(c, 'utf-8')
