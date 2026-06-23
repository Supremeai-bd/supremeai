#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

B = chr  # Bangla builder via unicode code points

ROOT = Path(r"C:\Users\n\supremeai\supremeai_2.0")

SKIP = [
    '.git', 'node_modules', '__pycache__', '.venv',
    '.turbo', 'dist', 'build', '.next', 'coverage', '.vitest',
]

EXTS = {'.py', '.ts', '.tsx', '.js', '.jsx', '.sh', '.yml', '.yaml', '.tf', '.toml', '.cfg', '.ini', '.Dockerfile', '.json'}

BN_FILE = B(0x09ab)+B(0x09be)+B(0x0982)+B(0x09b2)+B(0x09be)+' >> ' + B(0x09ab)+B(0x09be)+B(0x0982)+B(0x09b2)+B(0x09be)

PY_HDR = '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n# ============================================================================\n# ' + BN_FILE + '\n# ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n# ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n# ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n# ============================================================================\n'
JS_HDR = '// ============================================================================\n// ' + BN_FILE + '\n// ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n// ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n// ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n// ============================================================================\n'
TSX_HDR = '// ============================================================================\n// ' + B(0x0995)+B(0x09cb)+B(0x09ae)+B(0x09cd)+B(0x09aa)+B(0x09cb)+B(0x09a8)+B(0x09c7)+B(0x09a8)+B(0x09cd)+B(0x099f) + ' >> {n}\n// ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n// ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n// ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n// ============================================================================\n'
SH_HDR = '#!/bin/bash\n# ============================================================================\n# ' + B(0x09b8)+B(0x09cd)+B(0x0995)+B(0x09cd)+B(0x09b0)+B(0x09bf)+B(0x09aa)+B(0x09cd)+B(0x099f) + ' >> {n}\\n# ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n# ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n# ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n# ============================================================================\n'
YAML_HDR = '# ============================================================================\n# ' + B(0x0995)+B(0x09cb)+B(0x09a8)+B(0x09ab)+B(0x09bf)+B(0x0997)+B(0x09be)+B(0x09b0)+B(0x09c7)+B(0x09b6)+B(0x09a8) + ' >> {n}\n# ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n# ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n# ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n# ============================================================================\n'
TF_HDR = '# ============================================================================\n# ' + B(0x099f)+B(0x09c7)+B(0x09b0)+B(0x09be)+B(0x09b0)+B(0x09ab)+B(0x09b0)+B(0x09cd)+B(0x09ae) + ' >> {n}\n# ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n# ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n# ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n# ============================================================================\n'
DF_HDR = '# ============================================================================\n# ' + B(0x09a1)+B(0x0995)+B(0x09be)+B(0x09b0)+B(0x09ab)+B(0x09cb)+B(0x09b2)+B(0x09c7)+B(0x09b0) + ' >> {n}\n# ' + B(0x09aa)+B(0x09cd)+B(0x09b0)+B(0x09cb)+B(0x099c)+B(0x09c7)+B(0x0995)+B(0x09cd)+B(0x099f) + ' >> SupremeAI 2.0\n# ' + B(0x09a8)+B(0x09cd)+B(0x09af)+B(0x09be)+B(0x09b8)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09a4)+B(0x09cd)+B(0x09ac) + ' >> {p}\n# ' + B(0x09ae)+B(0x09cb)+B(0x09a1)+B(0x09c1)+B(0x09b2) + ' >> {m}\n# ============================================================================\n'
JSON_HDR = '// ============================================================================\n// config >> {n}\n// projet >> SupremeAI 2.0\n// purpose >> {p}\n// module >> {m}\n// ============================================================================\n'

HEADERS = {
    '.py': lambda n,m,p: '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n' + PY_HDR.format(n=n, m=m, p=p),
    '.ts': lambda n,m,p: JS_HDR.format(n=n, m=m, p=p),
    '.tsx': lambda n,m,p: TSX_HDR.format(n=n, m=m, p=p),
    '.js': lambda n,m,p: JS_HDR.format(n=n, m=m, p=p),
    '.jsx': lambda n,m,p: TSX_HDR.format(n=n, m=m, p=p),
    '.sh': lambda n,m,p: SH_HDR.format(n=n, m=m, p=p),
    '.yml': lambda n,m,p: YAML_HDR.format(n=n, m=m, p=p),
    '.yaml': lambda n,m,p: YAML_HDR.format(n=n, m=m, p=p),
    '.tf': lambda n,m,p: TF_HDR.format(n=n, m=m, p=p),
    '.toml': lambda n,m,p: YAML_HDR.format(n=n, m=m, p=p),
    '.cfg': lambda n,m,p: YAML_HDR.format(n=n, m=m, p=p),
    '.ini': lambda n,m,p: YAML_HDR.format(n=n, m=m, p=p),
    '.Dockerfile': lambda n,m,p: DF_HDR.format(n=n, m=m, p=p),
    '.json': lambda n,m,p: JSON_HDR.format(n=n, m=m, p=p),
}

PURPOSES = {
    'main': 'App main entry point',
    'config': 'Configuration loading',
    'conf': 'Configuration management',
    'auth': 'User authentication',
    'routes': 'API route definitions',
    'admin': 'Admin panel and controls',
    'agent': 'AI agent management',
    'tool': 'Helper tools',
    'memory': 'Memory storage',
    'brain': 'AI brain and routing',
    'core': 'Core system functionality',
    'database': 'Database operations',
    'db': 'Database operations',
    'test': 'Unit testing and QC',
    'models': 'Data models',
    'services': 'Business logic',
    'service': 'Business service',
    'api': 'API client',
    'docker': 'Docker settings',
    'terraform': 'Infrastructure as code',
    'monitor': 'System monitoring',
    'monitoring': 'System monitoring',
    'health': 'Health check',
    'billing': 'Billing management',
    'payment': 'Payment gateway',
    'webhook': 'Webhook handling',
    'stream': 'Streaming data',
    'storage': 'File storage',
    'audit': 'Audit logging',
    'migration': 'Database migration',
    'migrations': 'Database migrations',
    'notification': 'Notification service',
    'marketplace': 'Skill marketplace',
    'evolution': 'Evolution engine',
    'swarm': 'Swarm orchestration',
    'skill': 'Skill registry',
    'chat': 'Chat interface',
    'editor': 'Code editor',
    'dashboard': 'Dashboards',
    'provider': 'VS Code providers',
    'handler': 'Event handlers',
    'store': 'State management',
    'language': 'Multilingual support',
    'vector': 'Vector store',
    'rag': 'RAG pipeline',
    'cost': 'Cost tracking',
    'security': 'Security middleware',
    'rate': 'Rate limiting',
    'circuit': 'Circuit breaker',
    'cache': 'Caching system',
    'cloud': 'Cloud provider',
    'gcp': 'GCP integration',
    'firebase': 'Firebase integration',
    'supabase': 'Supabase integration',
    'github': 'GitHub integration',
    'discord': 'Discord bot',
    'email': 'Email service',
    'voice': 'Voice and TTS',
    'image': 'Image generation',
    'video': 'Video generation',
    'browser': 'Browser automation',
    'legal': 'Legal agent',
    'medical': 'Medical agent',
    'research': 'Research agent',
    'trading': 'Trading agent',
    'scientific': 'Scientific agent',
    'code': 'Code analysis',
    'feedback': 'Feedback service',
    'rbac': 'Role-based access',
    'tenant': 'Multi-tenant',
    'sso': 'Single sign-on',
    'ocr': 'OCR and document',
    'nlp': 'Natural language',
    'bangla': 'Bangla NLP',
    'bengali': 'Bengali OCR',
    'notifications': 'Notifications',
    'checkpoint': 'Checkpoint manager',
    'rollback': 'Rollback monitor',
    'idempotency': 'Idempotency',
    'observability': 'Observability',
    'telemetry': 'Telemetry',
    'honeypot': 'Honeypot middleware',
    'prompt': 'Prompt firewall',
    'input': 'Input sanitization',
    'output': 'Output validation',
    'semantic': 'Semantic cache',
    'free': 'Free tier tracker',
    'cost_auditor': 'Cost auditor',
    'posthog': 'PostHog analytics',
    'discord_bot': 'Discord bot',
    'factual': 'Factual verifier',
    'generation': 'Generation monitor',
    'evolution_engine': 'Evolution engine',
    'rules': 'Rules management',
    'token': 'Token budget',
    'task': 'Task routing',
    'mcp': 'MCP tools',
    'sandbox': 'Sandbox isolation',
    'pgbouncer': 'PgBouncer pool',
    'postgres': 'PostgreSQL store',
    'chromadb': 'ChromaDB vector',
    'sqlite': 'SQLite store',
    'episodic': 'Episodic memory',
    'long_term': 'Long-term memory',
    'sliding': 'Sliding window',
    'summary': 'Summary tree',
    'rag_pipeline': 'RAG pipeline',
    'rag': 'RAG retrieval',
    'validator': 'Code validators',
    'auto': 'Auto remediation',
    'dashboard_admin': 'Admin dashboard',
    'god': 'God mode',
    'orchestrator': 'Agent orchestration',
    'crewai': 'CrewAI',
    'langgraph': 'LangGraph',
    'parallel': 'Parallel routing',
    'fine': 'Fine-tuning',
    'rlhf': 'RLHF',
    'onboarding': 'User onboarding',
    'preferences': 'User preferences',
    'legal_agent': 'Legal agent',
    'medical_agent': 'Medical agent',
    'trading_agent': 'Trading agent',
    'research_assistant': 'Research assistant',
    'email_agent': 'Email agent',
    'github_agent': 'GitHub agent',
    'marketplace_agent': 'Marketplace agent',
    'pr_reviewer': 'PR reviewer',
    'vision': 'Vision agent',
    'game': 'Game dev agent',
    'scientific_agent': 'Scientific agent',
    'plan_sorter': 'Plan sorter',
    'style': 'Style learning',
    'preference': 'Preference memory',
    'domain': 'Domain adapter',
    'ensemble': 'Ensemble routing',
    'multi_account': 'Multi-account',
    'vpn': 'VPN switching',
    'bandwidth': 'Bandwidth optimization',
    'browser_agent': 'Browser agent',
    'model_trainer': 'Model trainer',
    'sync': 'Feature sync',
    'skill_recommender': 'Skill recommender',
    'bangla_ai': 'Bangla AI connector',
    'bengali_ocr': 'Bengali OCR',
    'cloud_sandbox': 'Cloud sandbox',
    'docker_sandbox': 'Docker sandbox',
    'computer': 'Computer agent',
    'playwright': 'Playwright agent',
    'checkpoint_manager': 'Checkpoint manager',
    'seed': 'Database seed',
    'video_generator': 'Video generation',
    'image_generator': 'Image generation',
    'viral': 'Viral referral',
    'parallel_agent': 'Parallel executor',
    'sync_features': 'Feature sync utility',
    'supreme_context_builder': 'Context builder',
    'skill_loader': 'Skill loader',
    'api_gateway': 'API gateway',
    'supreme_risk_scorer': 'Risk scoring',
    'supreme_docker_analyzer': 'Docker analysis',
    'supreme_config_audit': 'Config audit',
    'docker_ai_guard': 'Docker guard',
    'config_audit': 'Config audit',
    'package_json': 'Package config',
    'tsconfig': 'TypeScript config',
    'vite_config': 'Vite config',
    'turbo_json': 'Turborepo config',
    'kilo_json': 'Kilo project config',
    'docker_compose': 'Docker compose config',
    'firebase_json': 'Firebase configuration',
    'railway_json': 'Railway configuration',
    'render_yaml': 'Render configuration',
    'pre_commit_config': 'Pre-commit hooks config',
    'compliance_rules': 'Compliance config',
    'docker_limits': 'Docker limits config',
    'audit_rules': 'Audit rules config',
    'firestore_indexes': 'Firestore indexes',
    'openapi_spec': 'OpenAPI specification',
}


def get_module(fp):
    parts = list(fp.relative_to(ROOT).parts)
    if not parts:
        return 'root'
    if parts[0] == 'backend' and len(parts) > 1:
        return parts[1]
    if parts[0] == 'apps' and len(parts) > 2:
        return parts[2]
    return parts[0]


def get_purpose(stem):
    n = stem.lower()
    for k, v in PURPOSES.items():
        if k in n:
            return v
    return 'General utility'


def is_code(line):
    s = line.strip()
    if not s:
        return False
    if s.startswith('#') or s.startswith('//') or s.startswith('/*') or s.startswith('*'):
        return False
    if set(s) <= {'=', ' ', '#', '/', '*', '-', '~'}:
        return False
    for pat in ['import ', 'from ', 'export ', 'const ', 'let ', 'var ', 'function ', 'class ', 'def ', 'async ', 'await ', 'return ', 'if ', 'for ', 'while ', 'try:', 'with ', 'elif', 'else:', 'except', 'finally:', 'raise ', 'yield ', 'match ', 'case ', 'lambda', 'print(', 'logging.', 'app.', 'router.', 'FastAPI(', 'APIRouter(', 'Blueprint(', '# !', '<?php', '<html', '<!DOCTYPE', 'package ', 'require(', 'module.', 'describe(', 'test(', 'it(', 'beforeEach(', '@', 'namespace ', 'interface ', 'type ', 'enum ', 'public ', 'private ', 'protected ', 'static ', 'void ', 'int ', 'string ']:
        if s.startswith(pat):
            return True
    return bool(re.search(r'\b(def|class|import|from|return|if|else|elif|for|while|try|except|finally|with|async|await|yield|raise)\b', s))


def strip(content):
    lines = content.split('\n')
    idx = 0
    for i, ln in enumerate(lines):
        if is_code(ln):
            idx = i
            break
    body = lines[idx:]
    txt = '\n'.join(body)
    return txt.lstrip('\n')


def main():
    print("=" * 70)
    print("SupremeAI 2.0 - Bangla Comment Injection")
    print("=" * 70)
    
    files = []
    for root, dirs, fnames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.')]
        for f in fnames:
            fp = Path(root) / f
            r = str(fp.relative_to(ROOT))
            if any(p in r for p in SKIP):
                continue
            ext = fp.suffix.lower()
            if ext in EXTS:
                files.append(fp)
    
    print(f"Total: {len(files)}\n")
    
    ok = 0
    for i, fp in enumerate(files, 1):
        try:
            txt = fp.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        
        ext = fp.suffix.lower()
        hfn = HEADERS.get(ext)
        if not hfn:
            continue
        
        hdr = hfn(fp.name, get_module(fp), get_purpose(fp.stem))
        try:
            fp.write_text(hdr + strip(txt), encoding='utf-8')
            ok += 1
        except Exception:
            pass
        
        if i % 100 == 0 or i == len(files):
            print(f"{i}/{len(files)} ok={ok}")
    
    print("\nDONE: %d files" % ok)


if __name__ == '__main__':
    main()
