import os
import re

replacements = {
    r'from core\.security\.auth_middleware': r'from core.security.authentication.auth_middleware',
    r'from core\.security\.security_middleware': r'from core.security.protection.security_middleware',
    r'from core\.security\.secret_hunter': r'from core.security.scanning.secret_hunter',
    r'from core\.security\.security_regression': r'from core.security.audit.security_regression',
    r'from core\.security\.behavioral_analyzer': r'from core.security.intelligence.behavioral_analyzer',
    r'from p2p\.credit_system': r'from core.p2p.credit_system',
    r'from p2p\.secure_tunnel': r'from core.p2p.secure_tunnel',
    r'import p2p\.credit_system': r'import core.p2p.credit_system',
    r'import p2p\.secure_tunnel': r'import core.p2p.secure_tunnel',
    r'from scout\.knowledge_extractor': r'from services.scout.knowledge_extractor',
    r'from scout\.web_crawler_agent': r'from services.scout.web_crawler_agent',
    r'import scout\.knowledge_extractor': r'import services.scout.knowledge_extractor',
    r'import scout\.web_crawler_agent': r'import services.scout.web_crawler_agent',
    r'from core\.security\.honeypot_middleware': r'from core.security.protection.honeypot_middleware',
    r'from core\.security\.prompt_firewall': r'from core.security.protection.prompt_firewall',
    r'from core\.security\.rbac': r'from core.security.authentication.rbac',
    r'from core\.security\.microvm_sandbox': r'from core.security.sandbox.microvm_sandbox',
    r'from core\.security\.guardian_ai': r'from core.security.protection.guardian_ai',
    r'from core\.security\.compliance_bot': r'from core.security.audit.compliance_bot',
    r'from core\.security\.secure_credential_store': r'from core.security.authentication.secure_credential_store',
    r'from core\.security\.secret_vault': r'from core.security.protection.secret_vault',
    r'from core\.security\.resource_guard': r'from core.security.protection.resource_guard',
    r'from core\.security\.origin_validator': r'from core.security.protection.origin_validator',
    r'from core\.security\.input_sanitizer': r'from core.security.protection.input_sanitizer',
    r'from core\.security\.governance_policy': r'from core.security.audit.governance_policy',
    r'from core\.security\.audit_logger': r'from core.security.audit.audit_logger',
    r'from core\.security\.api_key_middleware': r'from core.security.authentication.api_key_middleware',
    r'from core\.security\.autonoguard_middleware': r'from core.security.protection.autonoguard_middleware',
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
                print(f'Updated {path}')
print(f'Total files updated: {count}')
