import os

policy_file = 'F:\\supremeai backup\\docs\\env_maintenance_policy.md'

keys_to_remove = [
    'RENDER_API_KEY_BACKUP',
    'RENDER_DEPLOY_HOOK_URL_BACKUP',
    'MIRROR_REPO_TOKEN',
    'STAGING_REPO_TOKEN',
    'SECONDARY_SERVICE_ACCOUNT_KEY'
]

def clean_file(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if any(k in line for k in keys_to_remove):
            continue
        new_lines.append(line)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

clean_file(policy_file)
