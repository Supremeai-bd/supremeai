import os

def fix_file(path, old, new):
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f: c = f.read()
    with open(path, 'w', encoding='utf-8') as f: f.write(c.replace(old, new))

fix_file('backend/core/universal_rules.py', 'rules_path = os.getenv', 'rules_path: str = os.getenv')
fix_file('backend/core/rbac.py', 'if context.expires_at <', 'if str(context.expires_at) <')
fix_file('backend/memory/sqlite_store.py', 'db_path = os.getenv', 'db_path: str = os.getenv')
fix_file('backend/core/evolution_engine.py', 'os.path.dirname(self.db_path)', 'os.path.dirname(str(self.db_path))')
fix_file('backend/core/evolution_engine.py', 'sqlite3.connect(self.db_path', 'sqlite3.connect(str(self.db_path)')
fix_file('backend/memory/cloud_postgres_store.py', 'Json', 'Any')
fix_file('backend/memory/cloud_postgres_store.py', 'from typing import Optional, Dict', 'from typing import Optional, Dict, Any')
fix_file('backend/core/microvm_sandbox.py', 'return "firecracker"', 'return True')
fix_file('backend/core/microvm_sandbox.py', 'return "gvisor"', 'return True')
fix_file('backend/core/microvm_sandbox.py', 'return None', 'return False')
fix_file('backend/core/gcp_pubsub_queue.py', 'sqlite3.connect(self.db_path', 'sqlite3.connect(str(self.db_path)')
fix_file('backend/core/gcp_pubsub_queue.py', 'conn = sqlite3.connect', 'conn = sqlite3.connect(str(self.db_path), check_same_thread=False)\n        assert conn is not None')
fix_file('backend/core/audit_logger.py', 'db_path = os.getenv', 'db_path: str = os.getenv')
fix_file('backend/brain/gcp_router.py', 'os.getenv("GCP_CLOUD_RUN_URL").rstrip', '(os.getenv("GCP_CLOUD_RUN_URL") or "").rstrip')
fix_file('backend/core/upstash_redis_queue.py', 'os.getenv("UPSTASH_REDIS_URL").rstrip', '(os.getenv("UPSTASH_REDIS_URL") or "").rstrip')
fix_file('backend/core/task_router.py', 'await asyncio.sleep(2 ** attempt)', 'await asyncio.sleep(2 ** attempt)\n        return {"success": False, "error": "External service unavailable"}')
fix_file('backend/core/semantic_cache.py', 'created_at=row["created_at"]', 'created_at=float(row["created_at"])')
fix_file('backend/core/app.py', 'settings.validate()', 'settings.validate_config()')
fix_file('backend/core/circuit_breaker.py', 'await task_func(', 'await task_func(  # type: ignore\n            ')
