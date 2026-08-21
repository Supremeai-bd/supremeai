import re, os

# Find which Studio Client files call specific mismatched paths
search_paths = [
    '/api/agent/',
    '/api/agents',
    '/task/execute',
    '/admin/rules',
    '/api/v1/billing',
    '/api/v1/metrics',
    '/api/skills/install',
    '/api/skills/search',
    '/api/knowledge/search',
    '/api/knowledge/seed',
    '/api/session/',
    '/api/v1/swarm/stream',
]

print("=== STUDIO CLIENT FILES WITH MISMATCHED CALLS ===")
for root, dirs, files in os.walk('frontend/src'):
    for fn in files:
        if fn.endswith('.ts') or fn.endswith('.tsx'):
            fp = os.path.join(root, fn)
            try:
                with open(fp, encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
            except:
                continue
            for i, line in enumerate(lines, 1):
                for sp in search_paths:
                    if sp in line:
                        print(f'  {fp}:{i}: {line.strip()[:150]}')
                        break
