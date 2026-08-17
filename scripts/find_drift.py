import re, os, sys

# Extract ALL client API paths from Studio Client
print("=== STUDIO CLIENT API CALLS ===")
client_paths = set()
for root, dirs, files in os.walk('apps/studio-client/src'):
    for fn in files:
        if fn.endswith('.ts') or fn.endswith('.tsx'):
            fp = os.path.join(root, fn)
            try:
                with open(fp, encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except:
                continue
            # Find string literals that look like API paths
            paths = re.findall(r'["\x27](/(?:api/|v\d/|task/|admin-api/|chat/|voice/|skills/|websocket/|ws/)[^\x27"]+)["\x27]', content)
            for p in paths:
                # Also find template literals
                pass
            # Also find template literal paths
            tmpl_paths = re.findall(r'`(/[^`]+)`', content)
            for p in tmpl_paths:
                if any(x in p for x in ['/api/', '/v1/', '/task/', '/admin-api/', '/chat/', '/voice/', '/skills/', '/websocket', '/ws/']):
                    client_paths.add(p)
            # Find string paths
            str_paths = re.findall(r'["\x27]/?(/api/[^"\x27]+|//[^"\x27]+)["\x27]', content)
            for p in str_paths:
                if p.startswith('//'):
                    continue
            # Direct api paths in strings
            direct = re.findall(r'["\x27](/api/v1/[^"\x27]+|/[a-z]+/api/[^"\x27]*|admin-api/[^"\x27]+)["\x27]', content)
            for p in direct:
                client_paths.add('/' + p if not p.startswith('/') else p)
            # apiClient calls
            api_calls = re.findall(r'apiClient\.\w+\(\s*["\x27]([^"\x27]+)["\x27]', content)
            for p in api_calls:
                client_paths.add(p)
            # Direct fetch calls
            fetch_calls = re.findall(r'fetch\([\x27`"]?(/?api[^\x27`"]+)', content)
            for p in fetch_calls:
                if p.startswith('/api'):
                    client_paths.add(p)
                elif p.startswith('`'):
                    tmpl = re.findall(r'`([^`]+)`', content)
                    for t in tmpl:
                        if '/api' in t or '/admin-api' in t or '/task/' in t or '/chat/' in t or '/voice/' in t:
                            client_paths.add(t)

# Print all unique client paths
for p in sorted(client_paths):
    print(f'  CLIENT: {p}')

# Now extract backend routes
print("\n=== BACKEND ROUTES ===")
backend_routes = set()
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
            prefix = prefix_match.group(1) if prefix_match else ''
            routes = re.findall(r'@router\.(get|post|put|delete|patch)\("([^"]+)"', content)
            for method, path in routes:
                full_path = prefix + path
                backend_routes.add(full_path)
                if any(x in full_path for x in ['/api/', '/admin-api/', '/task/', '/chat/', '/voice/', '/skills/', '/v1/']):
                    print(f'  BACKEND: {method.upper()} {full_path}')

# Check for mismatches
print("\n=== POTENTIAL DRIFT ===")
for cp in sorted(client_paths):
    if cp in backend_routes:
        pass  # Matched
    else:
        print(f'  MISMATCH: Client calls {cp} but no backend route found')
