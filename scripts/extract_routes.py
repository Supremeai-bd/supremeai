import re, os, sys

# Backend route extraction
print("=== BACKEND ROUTES (key files) ===")
backend_routes = {}
base_dirs = ['backend/api/routes', 'backend/api/v1', 'backend/tools', 'backend/api']

for base_dir in base_dirs:
    if not os.path.exists(base_dir):
        continue
    for root, dirs, files in os.walk(base_dir):
        for fn in files:
            if not fn.endswith('.py') or '__pycache__' in root:
                continue
            fp = os.path.join(root, fn)
            try:
                with open(fp, encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except:
                continue
            prefix_match = re.search(r'prefix\s*=\s*"([^"]+)"', content)
            routes = re.findall(r'@router\.(get|post|put|delete|patch)\("([^"]+)"', content)
            if routes:
                prefix = prefix_match.group(1) if prefix_match else ''
                for method, path in routes:
                    full_path = prefix + path
                    backend_routes[full_path] = (method, fn)
                    print(f'  {method.upper()} {full_path}  [{fn}]')

print(f'\nTotal backend routes: {len(backend_routes)}')
sys.stdout.flush()

# Also extract admin-dashboard specific routes
print("\n=== ADMIN DASHBOARD ROUTES ===")
fp = 'backend/api/routes/admin_dashboard.py'
try:
    with open(fp, encoding='utf-8', errors='replace') as f:
        content = f.read()
    prefix_match = re.search(r'prefix\s*=\s*"([^"]+)"', content)
    routes = re.findall(r'@router\.(get|post|put|delete|patch)\("([^"]+)"', content)
    prefix = prefix_match.group(1) if prefix_match else ''
    for method, path in routes:
        full_path = prefix + path
        print(f'  {method.upper()} {full_path}')
except Exception as e:
    print(f'Error: {e}')

# Poetry.lock extraction
print("\n=== POETRY.LOCK VERSIONS ===")
with open('backend/poetry.lock', encoding='utf-8') as f:
    content = f.read()
for pkg_name in ['litellm', 'cryptography', 'fastapi', 'pydantic', 'uvicorn', 'openai', 'anthropic']:
    # Find the package block: name = "pkg_name"\nversion = "x.y.z"
    pattern = r'name = "' + pkg_name + r'"\nversion = "([^"]+)"'
    matches = re.findall(pattern, content)
    if matches:
        print(f'  {pkg_name}: {matches}')
    else:
        # Try without word boundary issues
        pattern2 = r'name = "' + pkg_name + r'"[^}]*?version = "([^"]+)"'
        matches2 = re.findall(pattern2, content, re.DOTALL)
        if matches2:
            print(f'  {pkg_name}: {matches2}')
        else:
            print(f'  {pkg_name}: NOT FOUND')
