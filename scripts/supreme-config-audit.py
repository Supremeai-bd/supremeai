#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> supreme-config-audit.py
# project >> SupremeAI 2.0
# purpose >> Configuration loading
# module >> scripts
# ============================================================================
import os
import json
import re
import yaml
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path):
        return {}

try:
    from deepdiff import DeepDiff
except ImportError:
    class DeepDiff:
        def __init__(self, c1, c2, ignore_order=True):
            self.c1 = c1
            self.c2 = c2
        def get(self, key, default):
            if key == 'dictionary_item_added':
                return [f"root['{k}']" for k in self.c2 if k not in self.c1]
            if key == 'dictionary_item_removed':
                return [f"root['{k}']" for k in self.c1 if k not in self.c2]
            return default

class SupremeConfigAuditor:
    def __init__(self, envs):
        self.envs = envs
        self.issues = []
        self.autoFixed = []
        self.rules = self.load_rules()
        
    def load_rules(self):
        rules_path = Path("config/audit-rules.yml")
        if rules_path.exists():
            with open(rules_path, "r") as f:
                return yaml.safe_load(f)
        return {
            'risk_rules': {
                'CRITICAL': [
                    {'pattern': r'SECRET_KEY=.*', 'message': 'Hardcoded secrets'},
                    {'pattern': r'PASSWORD=.*[^*]', 'message': 'Plain passwords'},
                    {'pattern': r'API_KEY=sk-live', 'message': 'Live keys in non-prod'},
                    {'pattern': r'DEBUG=true', 'message': 'Debug in prod'}
                ],
                'HIGH': [
                    {'pattern': r'DATABASE_URL=.*localhost', 'message': 'Local DB in staging+'},
                    {'pattern': r'REDIS_URL=.*localhost', 'message': 'Local Redis in staging+'},
                    {'pattern': r'LOG_LEVEL=debug', 'message': 'Verbose logging in prod'}
                ],
                'MEDIUM': []
            },
            'required_envs': {
                'development': ['DATABASE_URL', 'REDIS_URL', 'API_KEY'],
                'staging': ['DATABASE_URL', 'REDIS_URL', 'API_KEY', 'SENTRY_DSN'],
                'production': ['DATABASE_URL', 'REDIS_URL', 'API_KEY', 'SENTRY_DSN', 'SSL_CERT']
            }
        }
        
    def audit(self):
        env_configs = {}
        
        # Load all env files
        for env in self.envs:
            env_file = f'.env.{env}'
            if os.path.exists(env_file):
                env_configs[env] = dotenv_values(env_file)
            elif env == 'development' and os.path.exists('.env'):
                env_configs[env] = dotenv_values('.env')
        
        # Cross-environment comparison
        for i, env1 in enumerate(self.envs):
            for env2 in self.envs[i+1:]:
                if env1 in env_configs and env2 in env_configs:
                    self.compare_envs(env1, env_configs[env1], 
                                    env2, env_configs[env2])
        
        # Required variables check
        for env, config in env_configs.items():
            self.check_required(env, config)
        
        # Secret scanning
        for env, config in env_configs.items():
            self.scan_secrets(env, config)
        
        return {
            'issues': self.issues,
            'autoFixed': self.autoFixed,
            'has_safe_fixes': 'true' if len(self.autoFixed) > 0 else 'false'
        }
    
    def compare_envs(self, env1, config1, env2, config2):
        """Find meaningful differences between environments"""
        diff = DeepDiff(config1, config2, ignore_order=True)
        
        added = diff.get('dictionary_item_added', [])
        removed = diff.get('dictionary_item_removed', [])
        
        all_diff_keys = []
        for key in added:
            var_name = key.split('[')[-1].strip("']")
            all_diff_keys.append((var_name, env2, env1))
        for key in removed:
            var_name = key.split('[')[-1].strip("']")
            all_diff_keys.append((var_name, env1, env2))
            
        for var_name, missing_in, present_in in all_diff_keys:
            self.issues.append({
                'risk': 'MEDIUM',
                'file': f'.env.{missing_in}',
                'message': f'{var_name} is missing (present in .env.{present_in})',
                'suggestion': f'Add {var_name} to .env.{missing_in}'
            })
    
    def check_required(self, env, config):
        """Check required variables per environment"""
        required = self.rules.get('required_envs', {}).get(env, [])
        for var in required:
            if var not in config:
                self.issues.append({
                    'risk': 'HIGH',
                    'file': f'.env.{env}',
                    'message': f'Required variable {var} missing',
                    'suggestion': f'Add {var} to .env.{env}'
                })
    
    def scan_secrets(self, env, config):
        """Scan for hardcoded secrets and misconfigurations"""
        for key, value in config.items():
            full_line = f'{key}={value}'
            
            risk_rules = self.rules.get('risk_rules', {})
            for risk_level, rules in risk_rules.items():
                for rule in rules:
                    pattern = rule.get('pattern', '')
                    message = rule.get('message', f'Potential issue with {key}')
                    if re.match(pattern, full_line, re.IGNORECASE):
                        if self.is_expected(key, value, env):
                            continue
                            
                        self.issues.append({
                            'risk': risk_level,
                            'file': f'.env.{env}' if env != 'development' else '.env',
                            'message': f'{message}: {key}',
                            'suggestion': self.get_suggestion(key, env)
                        })
    
    def is_expected(self, key, value, env):
        """Determine if a config is expected for the environment"""
        expected = {
            'development': {
                'DATABASE_URL': ['localhost', '127.0.0.1'],
                'DEBUG': ['true'],
                'LOG_LEVEL': ['debug']
            }
        }
        
        env_expected = expected.get(env, {})
        if key in env_expected:
            return any(exp in str(value) for exp in env_expected[key])
        return False
    
    def get_suggestion(self, key, env):
        """Get fix suggestion"""
        suggestions = {
            'DATABASE_URL': f'Use environment-specific DB URL for {env}',
            'SECRET_KEY': 'Use GitHub Secrets or AWS Secrets Manager',
            'API_KEY': f'Use {env}-specific API key from vault',
            'DEBUG': 'Set to false in production'
        }
        return suggestions.get(key, 'Review and fix manually')

if __name__ == '__main__':
    envs = os.getenv('ENVIRONMENTS', 'development,staging,production').split(',')
    auditor = SupremeConfigAuditor(envs)
    result = auditor.audit()
    
    # Save report to github output or file
    with open("audit_report.json", "w") as f:
        json.dump(result, f, indent=2)
        
    # Print the json so it can be captured by the workflow
    print(json.dumps(result))
