import re

with open('backend/api/routers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Change knowledge router prefix from "" to "/api"
content = content.replace(
    '("api.routes.knowledge", "")',
    '("api.routes.knowledge", "/api")'
)

with open('backend/api/routers.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed: knowledge prefix changed to /api")

# Verify
with open('backend/api/routers.py', 'r', encoding='utf-8') as f:
    verify = f.read()
if '("api.routes.knowledge", "/api")' in verify:
    print("VERIFIED: knowledge prefix is now /api")
else:
    print("ERROR: knowledge prefix was not changed!")
