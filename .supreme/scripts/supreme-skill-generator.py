#!/usr/bin/env python3
"""
SupremeAI Dynamic Skill Generator
Auto-creates skills based on user requests and stores for reuse
"""

import os
import re
import yaml
import json
from pathlib import Path
from datetime import datetime
import hashlib
import sys

class SupremeSkillGenerator:
    SKILL_TEMPLATE = {
        'schema_version': '1.0',
        'required_fields': [
            'name', 'description', 'domain', 'subdomain', 
            'tags', 'version', 'author'
        ],
        'optional_fields': [
            'frameworks', 'auto_generate', 'prerequisites',
            'when_to_use', 'workflow', 'verification',
            'rationalizations', 'references'
        ]
    }
    
    DOMAINS = {
        'devops': {
            'subdomains': ['ci-cd', 'infrastructure', 'monitoring', 'security'],
            'common_frameworks': ['NIST-CSF', 'CIS', 'MITRE-ATT&CK']
        },
        'development': {
            'subdomains': ['frontend', 'backend', 'api', 'database'],
            'common_frameworks': ['OWASP', 'CWE', 'NIST-CSF']
        },
        'marketing': {
            'subdomains': ['seo', 'content', 'social', 'email'],
            'common_frameworks': ['GDPR', 'CAN-SPAM']
        }
    }
    
    def __init__(self, skills_dir='.supreme/skills'):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.skill_index = self._load_index()
    
    def _load_index(self):
        index_path = self.skills_dir / '.index.json'
        if index_path.exists():
            try:
                return json.loads(index_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {'skills': {}, 'patterns': {}}
    
    def _save_index(self):
        index_path = self.skills_dir / '.index.json'
        index_path.write_text(json.dumps(self.skill_index, indent=2), encoding="utf-8")
    
    def parse_request(self, user_request: str) -> dict:
        patterns = {
            r'(?i)(docker|container|image)': {
                'domain': 'devops',
                'subdomain': 'infrastructure',
                'tags': ['docker', 'container', 'security']
            },
            r'(?i)(env|config|environment)': {
                'domain': 'devops', 
                'subdomain': 'infrastructure',
                'tags': ['config', 'security', 'audit']
            },
            r'(?i)(test|ci|cd|pipeline)': {
                'domain': 'devops',
                'subdomain': 'ci-cd',
                'tags': ['testing', 'automation', 'pipeline']
            }
        }
        
        matched = {}
        for pattern, metadata in patterns.items():
            if re.search(pattern, user_request):
                matched.update(metadata)
                break
        
        if not matched:
            matched = {
                'domain': 'general',
                'subdomain': 'general',
                'tags': ['custom']
            }
        
        return {
            'request': user_request,
            'domain': matched.get('domain', 'general'),
            'subdomain': matched.get('subdomain', 'general'),
            'tags': matched.get('tags', []),
            'intent_hash': hashlib.md5(user_request.encode()).hexdigest()[:8]
        }
    
    def check_exists(self, spec: dict) -> tuple:
        intent_hash = spec['intent_hash']
        
        if intent_hash in self.skill_index['skills']:
            return True, [self.skill_index['skills'][intent_hash]]
        
        similar = []
        for skill_id, skill_meta in self.skill_index['skills'].items():
            spec_tags = set(spec['tags'])
            meta_tags = set(skill_meta.get('tags', []))
            if spec_tags and meta_tags:
                overlap = len(spec_tags & meta_tags)
                if overlap / len(spec_tags) > 0.7:
                    similar.append(skill_meta)
        
        return len(similar) > 0, similar
    
    def generate_skill(self, spec: dict, user_request: str) -> Path:
        skill_name = self._generate_name(spec, user_request)
        skill_dir = self.skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill_content = self._generate_skill_md(spec, user_request)
        (skill_dir / 'SKILL.md').write_text(skill_content, encoding="utf-8")
        
        (skill_dir / 'references').mkdir(parents=True, exist_ok=True)
        (skill_dir / 'references' / 'standards.md').write_text(
            self._generate_standards(spec), encoding="utf-8"
        )
        
        (skill_dir / 'scripts').mkdir(parents=True, exist_ok=True)
        
        self.skill_index['skills'][spec['intent_hash']] = {
            'name': skill_name,
            'domain': spec['domain'],
            'subdomain': spec['subdomain'],
            'tags': spec['tags'],
            'created': datetime.now().isoformat(),
            'usage_count': 0
        }
        self._save_index()
        
        return skill_dir
    
    def _generate_name(self, spec: dict, request: str) -> str:
        words = re.findall(r'\b\w+\b', request.lower())
        stop_words = {'a', 'an', 'the', 'for', 'to', 'in', 'on', 'with', 'and'}
        keywords = [w for w in words if w not in stop_words][:4]
        if not keywords:
            return f"skill-{spec['intent_hash']}"
        return '-'.join(keywords)
    
    def _generate_standards(self, spec: dict) -> str:
        return f"""# Standards for {spec['domain']} - {spec['subdomain']}
This document details standards and compliance protocols for dynamic skills under {spec['domain']}.
"""

    def _generate_skill_md(self, spec: dict, request: str) -> str:
        name = self._generate_name(spec, request)
        return f"""---
name: {name}
description: >-
  {request}
domain: {spec['domain']}
subdomain: {spec['subdomain']}
tags: {spec['tags']}
version: "1.0"
author: supreme-ai
auto_generate: true
generated_from: "{request}"
generated_at: {datetime.now().isoformat()}
---

## When to Use
- {request}

## Prerequisites
- Configure environment variables and target configs

## Workflow
1. Analyze request targets and local codebase structure.
2. Execute automated scripts to process request.
3. Verify changes.

## Verification
- Code builds and tests pass.

## Rationalizations
| Excuse | Rebuttal |
|--------|----------|
| "I'll do it manually" | Automation reduces errors by 90% |
| "It's too complex" | Break into smaller steps |
"""
    
    def get_or_create(self, user_request: str) -> dict:
        spec = self.parse_request(user_request)
        exists, similar = self.check_exists(spec)
        
        if exists:
            return {
                'status': 'exists',
                'skill': similar[0],
                'message': f'Skill already exists: {similar[0]["name"]}'
            }
        
        skill_path = self.generate_skill(spec, user_request)
        
        return {
            'status': 'created',
            'skill_path': str(skill_path),
            'message': f'New skill created: {skill_path.name}'
        }

if __name__ == '__main__':
    if len(sys.argv) > 1:
        req = " ".join(sys.argv[1:])
    else:
        req = "environment config audit and docker gatekeeper optimization"
        
    generator = SupremeSkillGenerator()
    result = generator.get_or_create(req)
    print(json.dumps(result, indent=2))
