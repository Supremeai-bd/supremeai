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
    '/api/telemetry/frontend-error',
    '/api/v1/agent/action',
    'admin-api/config',
    '/preferences/',
]

found = False
for root, dirs, files in os.walk('apps/studio-client/src'):
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
                        if not found:
                            found = True
                        print(f'  {fp}:{i}: {line.strip()[:200]}')
                        break

if not found:
    print("No matches found with those patterns")
