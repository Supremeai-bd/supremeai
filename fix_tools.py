import os
import re

replacements = {
    r'core\.security\.protection\.guardian_ai': r'core.security.intelligence.guardian_ai',
    r'core\.errors\.auto_healer': r'core.errors.auto_healer_service',
}

target_dir = r'f:\supremeai\backend\tools'
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
            
            new_content = content
            for pat, rep in replacements.items():
                new_content = re.sub(pat, rep, new_content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                count += 1
                print(f'Fixed {path}')
print(f'Total regex fixed: {count}')
