import os
import glob

def replace_in_file(filepath, replacements):
    if not os.path.exists(filepath):
        print(f'Missing: {filepath}')
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated: {filepath}')

def process_directory(directory, replacements, extensions=('.py', '.ts', '.tsx', '.json', '.js', '.sh')):
    for root, _, files in os.walk(directory):
        if 'node_modules' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith(extensions):
                replace_in_file(os.path.join(root, file), replacements)

# 1. Admin Email fallbacks
admin_replacements = [
    (', "admin@supremeai.com")', ', None)'),
    ('="admin@supremeai.com"', '="<admin-email>"'),
    ("'admin@supremeai.com'", "'<admin-email>'"),
    ('"admin@supremeai.com"', '"<admin-email>"')
]

# 2. Redis Localhost fallbacks
redis_replacements = [
    (', "redis://localhost:6379")', ', None)'),
    ('="redis://localhost:6379"', '="redis://<your-redis-url>"'),
    ("'redis://localhost:6379'", "'redis://<your-redis-url>'"),
    ('"redis://localhost:6379"', '"redis://<your-redis-url>"'),
    ('redis://localhost:6379', 'redis://<your-redis-url>'),
    ('redis://localhost', 'redis://<your-redis-url>')
]

# 3. Render URL fallbacks
render_replacements = [
    (' || "https://supremeai-backend-docker.onrender.com"', ''),
    (" || 'https://supremeai-backend-docker.onrender.com'", ""),
    (' || "supremeai-backend-docker.onrender.com"', ''),
    (" || 'supremeai-backend-docker.onrender.com'", ""),
    (', "https://supremeai-backend-docker.onrender.com")', ')'),
    ('"https://supremeai-backend-docker.onrender.com"', '"<backend-url>"'),
    ("'https://supremeai-backend-docker.onrender.com'", "'<backend-url>'"),
    ('"supremeai-backend-docker.onrender.com"', '"<backend-url>"'),
    ("'supremeai-backend-docker.onrender.com'", "'<backend-url>'")
]

process_directory(r'f:\supremeai\backend', admin_replacements + redis_replacements + render_replacements)
process_directory(r'f:\supremeai\frontend', admin_replacements + redis_replacements + render_replacements)
process_directory(r'f:\supremeai\scripts', admin_replacements + redis_replacements + render_replacements)
process_directory(r'f:\supremeai\infrastructure', admin_replacements + redis_replacements + render_replacements)
replace_in_file(r'f:\supremeai\firebase.json', render_replacements)
