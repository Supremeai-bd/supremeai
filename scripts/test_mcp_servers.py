import os
import sys
import importlib.util
import traceback

repo_root = r'f:\supremeai'
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'backend'))

mcp_dir = os.path.join(repo_root, 'backend', 'tools', 'mcp')
files = [f for f in sorted(os.listdir(mcp_dir)) if f.endswith('.py') and not f.startswith('__')]

print(f"=== TESTING {len(files)} MCP SCRIPTS ===")
results = {}

for f in files:
    file_path = os.path.join(mcp_dir, f)
    mod_name = f[:-3]
    try:
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results[f] = {'status': 'PASS', 'error': None}
    except Exception as e:
        results[f] = {'status': 'FAIL', 'error': f"{type(e).__name__}: {str(e)}"}

print("\n=== RESULTS ===")
for f, res in results.items():
    icon = '✅' if res['status'] == 'PASS' else '❌'
    err = res['error'] if res['error'] else 'Imports and initializes OK'
    print(f"{icon} {f} | {res['status']} | {err}")
