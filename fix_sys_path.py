import os
import re

target_dir = r'f:\supremeai\backend\tests'
count = 0
for root, _, files in os.walk(target_dir):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                continue
            
            # Remove sys.path.append(...)
            new_content = re.sub(r'sys\.path\.append\([^)]+\)\n', '', content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                count += 1
                print(f'Removed sys.path.append from {path}')
print(f'Total sys.path.append removed: {count}')
