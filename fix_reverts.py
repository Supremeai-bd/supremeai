import os
import re

replacements = {
    r'core\.security\.authentication\.secure_credential_store': r'core.security.secure_credential_store',
    r'core\.security\.protection\.secret_vault': r'core.security.secret_vault',
    r'core\.security\.protection\.resource_guard': r'core.security.resource_guard',
    r'core\.security\.protection\.origin_validator': r'core.security.origin_validator',
    r'core\.security\.protection\.input_sanitizer': r'core.security.input_sanitizer',
    r'core\.security\.audit\.governance_policy': r'core.security.governance_policy',
    r'core\.security\.audit\.audit_logger': r'core.security.audit_logger',
    r'core\.security\.authentication\.api_key_middleware': r'core.security.api_key_middleware',
    r'core\.security\.protection\.autonoguard_middleware': r'core.security.autonoguard_middleware',
}

target_dir = r'f:\supremeai\backend'
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
                print(f'Reverted {path}')
print(f'Total reverted: {count}')
