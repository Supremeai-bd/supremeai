import os

files_with_logger = [
    r'F:\supremeai\backend\core\factual_verifier.py',
    r'F:\supremeai\backend\engine\vector_db.py',
    r'F:\supremeai\backend\memory\chromadb_store.py'
]

for p in files_with_logger:
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace('_logger.', 'logger.')
    if 'from loguru import logger' not in content:
        content = 'from loguru import logger\n' + content
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)

p = r'F:\supremeai\backend\core\health\proactive_healer.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()
if 'from loguru import logger' not in content:
    content = 'from loguru import logger\n' + content
with open(p, 'w', encoding='utf-8') as f:
    f.write(content)

files_with_future = [
    r'F:\supremeai\backend\core\llm\telemetry.py',
    r'F:\supremeai\backend\core\security\__init__.py',
    r'F:\supremeai\backend\memory\mcp_server.py',
    r'F:\supremeai\backend\pyerrorfix\detectors\logging_err.py'
]

for p in files_with_future:
    with open(p, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    future_line = ''
    new_lines = []
    for line in lines:
        if 'from __future__ import annotations' in line:
            future_line = line
        else:
            new_lines.append(line)
    
    if future_line:
        insert_idx = 0
        new_lines.insert(insert_idx, future_line)
    
    with open(p, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
