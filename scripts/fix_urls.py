import os
import re

search_regex = re.compile(r'supremeai-backend(?:-docker)?\.onrender\.com')
replace_str = 'api.example.com'

count = 0
for root, dirs, files in os.walk('.'):
    if any(ignore in root for ignore in ['.git', 'node_modules', '.venv', '__pycache__', '.pytest_cache']):
        continue
    for file in files:
        if file.endswith('.md') or file.endswith('.py') or file.endswith('.yml'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
                continue
            if search_regex.search(content):
                new_content = search_regex.sub(replace_str, content)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
                count += 1
print(f"Done! Updated {count} files.")
