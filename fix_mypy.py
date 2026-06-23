import os
import re

def fix(path, old, new):
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f: c = f.read()
    with open(path, 'w', encoding='utf-8') as f: f.write(c.replace(old, new))

def fix_re(path, pattern, new):
    if not os.path.exists(path): return
    with open(path, 'r', encoding='utf-8') as f: c = f.read()
    c, n = re.subn(pattern, new, c)
    if n > 0:
        with open(path, 'w', encoding='utf-8') as f: f.write(c)

fix('backend/memory/sliding_window.py', 'def __init__(self, db_path: str = None, config: SlidingWindowConfig = None):', 'def __init__(self, db_path: typing.Optional[str] = None, config: typing.Optional[SlidingWindowConfig] = None):')
fix_re('backend/memory/sliding_window.py', r'^import sqlite3\n', 'import sqlite3\nimport typing\n')

fix('backend/memory/cloud_postgres_store.py', 'Any(row[4])', 'row[4]')

fix('backend/brain/autonomous_agent.py', 'self.skill_creator = None', 'self.skill_creator: typing.Any = None')
fix_re('backend/brain/autonomous_agent.py', r'^import json\n', 'import json\nimport typing\n')

fix('backend/core/gcp_pubsub_queue.py', 'self._memory_conn = None', 'self._memory_conn: typing.Any = None')
fix_re('backend/core/gcp_pubsub_queue.py', r'^import json\n', 'import json\nimport typing\n')

fix('backend/core/audit_logger.py', 'db_path: str = None', 'db_path: typing.Optional[str] = None')
fix_re('backend/core/audit_logger.py', r'^import sqlite3\n', 'import sqlite3\nimport typing\n')

fix('backend/memory/checkpoint_resume.py', 'db_path: str = None', 'db_path: typing.Optional[str] = None')
fix_re('backend/memory/checkpoint_resume.py', r'^import json\n', 'import json\nimport typing\n')

fix('backend/tools/gcp_cloud_functions.py', 'os.getenv("GCP_PROJECT_ID").rstrip', '(os.getenv("GCP_PROJECT_ID") or "").rstrip')

fix('backend/core/semantic_cache.py', 'vector = json.loads(row["vector"]) if row["vector"] else None', 'vector = json.loads(str(row["vector"])) if row["vector"] else None')

fix('backend/tools/local_search_rag.py', 'query_tf = {}', 'query_tf: typing.Dict[str, float] = {}')
fix('backend/tools/local_search_rag.py', 'self.index.upsert', 'if self.index: self.index.upsert')
fix_re('backend/tools/local_search_rag.py', r'^import math\n', 'import math\nimport typing\n')

fix('backend/api/routes/task.py', 'instance: str = None', 'instance: typing.Optional[str] = None')
fix_re('backend/api/routes/task.py', r'^from typing import ', 'import typing\nfrom typing import ')

fix('backend/api/routes/simulator.py', 'PROFILES = {}', 'PROFILES: typing.Dict[str, typing.Any] = {}')
fix('backend/api/routes/simulator.py', 'SESSIONS = {}', 'SESSIONS: typing.Dict[str, typing.Any] = {}')
fix_re('backend/api/routes/simulator.py', r'^from fastapi import', 'import typing\nfrom fastapi import')

fix('backend/api/routes/cdc_webhooks.py', 'doc_id: str = None', 'doc_id: typing.Optional[str] = None')
fix_re('backend/api/routes/cdc_webhooks.py', r'^import json\n', 'import json\nimport typing\n')

fix('backend/api/routes/knowledge.py', 'LocalSearchRAGClass = None', 'LocalSearchRAGClass: typing.Any = None')
fix('backend/api/routes/knowledge.py', 'KnowledgeBaseIndexerClass = None', 'KnowledgeBaseIndexerClass: typing.Any = None')
fix('backend/api/routes/knowledge.py', 'except ImportError:\n    sqlite3 = None', 'except ImportError:\n    sqlite3: typing.Any = None')

fix('backend/tools/cost_auditor.py', 'db_path: str = None', 'db_path: typing.Optional[str] = None')
fix_re('backend/tools/cost_auditor.py', r'^import sqlite3\n', 'import sqlite3\nimport typing\n')

fix('backend/core/gcp_firestore.py', 'self._memory_conn = None', 'self._memory_conn: typing.Any = None')
fix_re('backend/core/gcp_firestore.py', r'^import json\n', 'import json\nimport typing\n')

fix('backend/core/app.py', 'self.client = None', 'self.client: typing.Any = None')
fix('backend/core/app.py', 'self.http_client = None', 'self.http_client: typing.Any = None')

fix('backend/core/auto_remediation.py', 'gemini_api_key: str = None', 'gemini_api_key: typing.Optional[str] = None')
fix_re('backend/core/auto_remediation.py', r'^import json\n', 'import json\nimport typing\n')

# model_router async iterators
fix('backend/brain/model_router.py', '-> Iterator[str]', '-> typing.Any')
fix_re('backend/brain/model_router.py', r'^import json\n', 'import json\nimport typing\n')

