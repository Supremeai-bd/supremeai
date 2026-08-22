import os
import re

replacements = {
    r'from core\.security\.ast_sandbox_scanner': r'from core.security.scanning.ast_scanner',
    r'core\.security\.protection\.honeypot_middleware': r'core.security.protection.honeypot',
    r'core\.security\.scanning\.secret_hunter': r'core.security.scanning.secret_scanner',
    r'from core\.p2p\.credit_system': r'from p2p.credit_system',
    r'from core\.p2p\.secure_tunnel': r'from p2p.secure_tunnel',
    r'import services\.scout\.knowledge_extractor': r'import scout.knowledge_extractor',
    r'from services\.scout\.web_crawler_agent': r'from scout.web_crawler_agent',
    r'\"core\.security\.protection\.honeypot_middleware': r'"core.security.protection.honeypot',
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
                print(f'Fixed final error {path}')
print(f'Total final fixes: {count}')
