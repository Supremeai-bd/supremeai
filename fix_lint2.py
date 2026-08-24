import os
import re

# 1. trio_adapters.py
p = r'F:\supremeai\backend\agents\ide\trio_adapters.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()
c = re.sub(r'        if not logger\.handlers:\n        logger\.addHandler\(logging\.NullHandler\(\)\)', r'    if not hasattr(logger, "handlers") or not logger.handlers:\n        pass', c)
with open(p, 'w', encoding='utf-8') as f:
    f.write(c)

# 2. memory.py
p = r'F:\supremeai\backend\api\routes\memory.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('    from loguru import logger\n\n        try:', '    from loguru import logger\n\n    try:')
lines = c.split('\n')
for i, l in enumerate(lines):
    if l.startswith('        except Exception as e:'):
        lines[i] = '    except Exception as e:'
    if l.startswith('            logger.error(f"Failed to list conversations: {e}")'):
        lines[i] = '        logger.error(f"Failed to list conversations: {e}")'
    if l.startswith('            raise HTTPException(status_code=500, detail=str(e)) from e'):
        lines[i] = '        raise HTTPException(status_code=500, detail=str(e)) from e'
with open(p, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

# 3. telemetry.py
p = r'F:\supremeai\backend\api\v1\telemetry.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('    from loguru import logger\n\n        logger.error(', '    from loguru import logger\n\n    logger.error(')
with open(p, 'w', encoding='utf-8') as f:
    f.write(c)

# 4. chat.py
p = r'F:\supremeai\backend\api\routes\chat.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()
if 'from loguru import logger' not in c:
    c = 'from loguru import logger\n' + c
with open(p, 'w', encoding='utf-8') as f:
    f.write(c)
