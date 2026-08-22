import os
import re

replacements = {
    r'\"core\.security\.auth_middleware': r'"core.security.authentication.auth_middleware',
    r'\"core\.security\.security_middleware': r'"core.security.protection.security_middleware',
    r'\"core\.security\.secret_hunter': r'"core.security.scanning.secret_hunter',
    r'\"core\.security\.security_regression': r'"core.security.audit.security_regression',
    r'\"core\.security\.behavioral_analyzer': r'"core.security.intelligence.behavioral_analyzer',
    r'\"p2p\.credit_system': r'"core.p2p.credit_system',
    r'\"p2p\.secure_tunnel': r'"core.p2p.secure_tunnel',
    r'\"scout\.knowledge_extractor': r'"services.scout.knowledge_extractor',
    r'\"scout\.web_crawler_agent': r'"services.scout.web_crawler_agent',
    r'\"core\.security\.honeypot_middleware': r'"core.security.protection.honeypot_middleware',
    r'\"core\.security\.prompt_firewall': r'"core.security.protection.prompt_firewall',
    r'\"core\.security\.rbac': r'"core.security.authentication.rbac',
    r'\"core\.security\.microvm_sandbox': r'"core.security.sandbox.microvm_sandbox',
    r'\"core\.security\.guardian_ai': r'"core.security.protection.guardian_ai',
    r'\"core\.security\.compliance_bot': r'"core.security.audit.compliance_bot',
    r'\"core\.security\.secure_credential_store': r'"core.security.authentication.secure_credential_store',
    r'\"core\.security\.secret_vault': r'"core.security.protection.secret_vault',
    r'\"core\.security\.resource_guard': r'"core.security.protection.resource_guard',
    r'\"core\.security\.origin_validator': r'"core.security.protection.origin_validator',
    r'\"core\.security\.input_sanitizer': r'"core.security.protection.input_sanitizer',
    r'\"core\.security\.governance_policy': r'"core.security.audit.governance_policy',
    r'\"core\.security\.audit_logger': r'"core.security.audit.audit_logger',
    r'\"core\.security\.api_key_middleware': r'"core.security.authentication.api_key_middleware',
    r'\"core\.security\.autonoguard_middleware': r'"core.security.protection.autonoguard_middleware',
    r'\'core\.security\.auth_middleware': r"'core.security.authentication.auth_middleware",
    r'\'core\.security\.security_middleware': r"'core.security.protection.security_middleware",
    r'\'core\.security\.secret_vault': r"'core.security.protection.secret_vault",
}

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
            
            new_content = content
            for pat, rep in replacements.items():
                new_content = re.sub(pat, rep, new_content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                count += 1
                print(f'Updated {path}')
print(f'Total patch tests updated: {count}')
