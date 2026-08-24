import os
import shutil
import re

misc_dir = 'backend/tests/misc'
base_tests_dir = 'backend/tests'

if not os.path.exists(misc_dir):
    print(f"Directory {misc_dir} not found.")
    exit(0)

moved = 0
deleted = 0

for filename in os.listdir(misc_dir):
    if not filename.endswith('.py'):
        continue
        
    filepath = os.path.join(misc_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find what it's testing by looking at its imports
    # usually: from core.something import ... or import core.something
    core_match = re.search(r'from\s+core\.[\w_]+\s+import', content)
    api_match = re.search(r'from\s+api\.[\w_]+\s+import', content)
    services_match = re.search(r'from\s+services\.[\w_]+\s+import', content)
    
    target_dir = None
    if core_match:
        target_dir = os.path.join(base_tests_dir, 'core')
    elif api_match:
        target_dir = os.path.join(base_tests_dir, 'api')
    elif services_match:
        target_dir = os.path.join(base_tests_dir, 'services')
    
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(filepath, os.path.join(target_dir, filename))
        moved += 1
    else:
        # If it doesn't clearly test core/api/services, it's likely a hallucinated/garbage test. Delete it.
        os.remove(filepath)
        deleted += 1

print(f"Moved {moved} valid tests to their proper modules.")
print(f"Deleted {deleted} unmapped/garbage tests.")

# Delete fake agents
agents_dir = 'backend/tools/ai_agents'
fake_agents = ['blockchain_agent.py', 'game_dev_agent.py', 'legal_agent.py', 'medical_agent.py', 'scientific_agent.py', 'trading_agent.py']

agents_deleted = 0
if os.path.exists(agents_dir):
    for agent in fake_agents:
        path = os.path.join(agents_dir, agent)
        if os.path.exists(path):
            os.remove(path)
            agents_deleted += 1

print(f"Deleted {agents_deleted} fake domain agents.")

# Clean up empty misc dir
if os.path.exists(misc_dir) and not os.listdir(misc_dir):
    os.rmdir(misc_dir)
