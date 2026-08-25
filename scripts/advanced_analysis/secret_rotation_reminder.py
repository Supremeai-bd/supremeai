#!/usr/bin/env python3
"""
Secret Rotation Reminder for SupremeAI
=======================================
Tracks age of secrets in Infisical/secrets registry and sends
reminders when secrets exceed rotation threshold.

Features:
- Scans various secret storage locations (Infisical, .env, etc.)
- Estimates secret age based on file modification time or metadata
- Flags secrets that may need rotation
- Generates rotation schedule recommendations

Usage:
    python secret_rotation_reminder.py [--project-root ../] [--threshold-days 90]
    
Self-healing principles:
- Auto-discovers secret files and configs
- No hardcoded secret names - fully dynamic
- CI-friendly output for security scanning
"""

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SecretEntry:
    """A secret/credential found in configuration."""
    name: str
    source: str  # 'infisical', '.env', 'render.yaml', etc.
    source_file: str
    last_modified: datetime | None = None
    estimated_age_days: int = 0  # Estimated from file mtime or other heuristics
    is_encrypted: bool = False
    has_rotation_policy: bool = False
    category: str = ""  # 'api_key', 'database', 'external_service', etc.
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL


@dataclass 
class RotationReminder:
    """A reminder that a secret needs rotation."""
    secret: SecretEntry
    days_since_rotation: int
    threshold_exceeded_by: int
    priority: str  # IMMEDIATE, SOON, SCHEDULED
    recommendation: str


@dataclass
class RotationReport:
    """Summary of secret rotation analysis."""
    total_secrets_found: int = 0
    secrets_needing_rotation: int = 0
    immediate_action: int = 0  # Over threshold significantly
    soon_needed: int = 0  # Approaching threshold
    well_managed: int = 0  # Within safe range
    by_category: dict[str, int] = field(default_factory=dict)
    by_source: dict[str, int] = field(default_factory=dict)


# Default rotation thresholds (in days) by category
ROTATION_THRESHOLDS = {
    'api_key': 90,
    'database': 180,
    'external_service': 90,
    'payment': 30,  # Payment keys should rotate frequently
    'encryption': 365,  # Encryption keys can be longer
    'jwt': 30,  # JWT secrets
    'oauth': 90,
    'webhook': 180,
    'internal': 365,  # Internal service keys
    'default': 90,
}

# High-risk secret name patterns
HIGH_RISK_PATTERNS = [
    r'password', r'passwd', r'secret', r'api_?key', r'token',
    r'private_?key', r'credential', r'auth',
]

PAYMENT_PATTERNS = [
    r'stripe', r'paypal', r'rezorpay', r'sslcommerz',
    r'payment', r'billing', r'checkout',
]


class SecretScanner:
    """Scans for secrets in various configurations."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.secrets: dict[str, SecretEntry] = {}
        
    def scan(self) -> dict[str, SecretEntry]:
        """Scan all known secret sources."""
        self._scan_env_files()
        self._scan_infisical_config()
        self._scan_render_yaml()
        self._scan_secrets_registry()
        self._scan_docker_files()
        
        logger.info(f"Found {len(self.secrets)} secret entries")
        return self.secrets
    
    def _categorize_secret(self, name: str) -> str:
        """Categorize a secret based on its name."""
        name_lower = name.lower()
        
        if any(p in name_lower for p in PAYMENT_PATTERNS):
            return 'payment'
        if any(p in name_lower for p in ['db_', 'database', 'mongo', 'postgres', 'redis']):
            return 'database'
        if any(p in name_lower for p in ['jwt', 'session', 'auth_token']):
            return 'jwt'
        if any(p in name_lower for p in ['oauth', 'social', 'github_', 'google_']):
            return 'oauth'
        if any(p in name_lower for p in ['encrypt', 'cipher', 'pem', 'key']):
            return 'encryption'
        if any(p in name_lower for p in ['webhook', 'callback']):
            return 'webhook'
        if any(p in name_lower for p in ['openai', 'anthropic', 'gemini', 'llm', 'ai_']):
            return 'external_service'
        
        return 'default'
    
    def _assess_risk(self, name: str, category: str) -> str:
        """Assess risk level of a secret."""
        name_lower = name.lower()
        
        # Critical patterns
        if category == 'payment':
            return 'CRITICAL'
        if any(p in name_lower for p in ['prod', 'production', 'live', 'master']):
            return 'HIGH'
        if any(p in name_lower for p in ['private', 'secret', 'credential']):
            return 'HIGH'
        
        # Medium risk
        if any(p in name_lower for p in HIGH_RISK_PATTERNS):
            return 'MEDIUM'
        
        return 'LOW'
    
    def _get_file_age(self, file_path: Path) -> int:
        """Estimate age of a file in days."""
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            age = (datetime.now() - mtime).days
            return max(0, age)
        except Exception:
            return 0  # Unknown age
    
    def _scan_env_files(self):
        """Scan .env files."""
        env_patterns = ['.env', '.env.local', '.env.production', '.env.development', '.env.staging']
        
        for pattern in env_patterns:
            env_file = self.project_root / pattern
            if env_file.exists():
                self._parse_env_file(env_file, pattern)
    
    def _parse_env_file(self, file_path: Path, source_name: str):
        """Parse an environment file for secrets."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        age = self._get_file_age(file_path)
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE (don't log values!)
            match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=', line)
            if match:
                key = match.group(1)
                
                # Skip non-sensitive keys
                if key.upper() in {'PORT', 'HOST', 'DEBUG', 'ENV', 'LOG_LEVEL', 'VERSION'}:
                    continue
                
                category = self._categorize_secret(key)
                risk = self._assess_risk(key, category)
                
                entry = SecretEntry(
                    name=key,
                    source=source_name,
                    source_file=rel_path,
                    last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
                    estimated_age_days=age,
                    is_encrypted=False,  # .env files are typically not encrypted
                    has_rotation_policy=False,
                    category=category,
                    risk_level=risk
                )
                
                self.secrets[f"{source_name}:{key}"] = entry
    
    def _scan_infisical_config(self):
        """Scan Infisical configuration files."""
        infisical_patterns = ['infisical.json', '.infisical.yaml', '.infisical.yml']
        
        for pattern in infisical_patterns:
            inf_file = self.project_root / pattern
            if inf_file.exists():
                self._parse_infisical_file(inf_file)
    
    def _parse_infisical_file(self, file_path: Path):
        """Parse Infisical config file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            if file_path.suffix == '.json':
                data = json.load(content) if isinstance(content, dict) else json.loads(content)
            else:
                import yaml
                data = yaml.safe_load(content)
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        age = self._get_file_age(file_path)
        
        # Extract secret names (not values!)
        if isinstance(data, dict):
            for section in ['secrets', 'environment', 'variables']:
                items = data.get(section, {})
                if isinstance(items, dict):
                    for key in items:
                        category = self._categorize_secret(key)
                        risk = self._assess_risk(key, category)
                        
                        entry = SecretEntry(
                            name=key,
                            source='infisical',
                            source_file=rel_path,
                            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
                            estimated_age_days=age,
                            is_encrypted=True,  # Infisical encrypts by default
                            has_rotation_policy=False,
                            category=category,
                            risk_level=risk
                        )
                        
                        self.secrets[f"infisical:{key}"] = entry
    
    def _scan_render_yaml(self):
        """Scan render.yaml for environment variables."""
        render_yaml = self.project_root / 'render.yaml'
        
        if render_yaml.exists():
            self._parse_render_yaml(render_yaml)
    
    def _parse_render_yaml(self, file_path: Path):
        """Parse render.yaml for secrets."""
        try:
            import yaml
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f)
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        age = self._get_file_age(file_path)
        
        services = content.get('services', [])
        if isinstance(services, dict):
            services = [services]
        
        for service in services:
            env_vars = service.get('envVars', [])
            for var in env_vars:
                if isinstance(var, dict):
                    key = var.get('key', '')
                    
                    # Skip non-sensitive
                    if key.upper() in {'PORT', 'ENV'}:
                        continue
                    
                    category = self._categorize_secret(key)
                    risk = self._assess_risk(key, category)
                    
                    entry = SecretEntry(
                        name=key,
                        source='render.yaml',
                        source_file=rel_path,
                        last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
                        estimated_age_days=age,
                        is_encrypted=False,
                        has_rotation_policy=False,
                        category=category,
                        risk_level=risk
                    )
                    
                    self.secrets[f"render:{key}"] = entry
    
    def _scan_secrets_registry(self):
        """Scan custom secrets registry."""
        registry_patterns = ['secrets_registry.yaml', 'secrets.json', '.secrets.yaml']
        
        for pattern in registry_patterns:
            reg_file = self.project_root / pattern
            if reg_file.exists():
                self._parse_secrets_registry(reg_file)
    
    def _parse_secrets_registry(self, file_path: Path):
        """Parse secrets registry file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            if file_path.suffix == '.json':
                data = json.loads(content)
            else:
                import yaml
                data = yaml.safe_load(content)
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        age = self._get_file_age(file_path)
        
        if isinstance(data, dict):
            for key in data:
                category = self._categorize_secret(key)
                risk = self._assess_risk(key, category)
                
                entry = SecretEntry(
                    name=key,
                    source='registry',
                    source_file=rel_path,
                    estimated_age_days=age,
                    category=category,
                    risk_level=risk
                )
                
                self.secrets[f"registry:{key}"] = entry
    
    def _scan_docker_files(self):
        """Scan docker-compose and Dockerfile for secrets."""
        docker_patterns = ['docker-compose.yml', 'docker-compose.yaml', 'Dockerfile']
        
        for pattern in docker_patterns:
            docker_file = self.project_root / pattern
            if docker_file.exists():
                self._parse_docker_file(docker_file)
    
    def _parse_docker_file(self, file_path: Path):
        """Parse Docker-related file for secrets."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        age = self._get_file_age(file_path)
        
        for i, line in enumerate(lines):
            # Look for ENV, secret references
            if 'SECRET' in line.upper() or 'PASSWORD' in line.upper() or 'API_KEY' in line.upper():
                match = re.search(r'(?:SECRET|PASSWORD|API_KEY|TOKEN)[_\w]*', line, re.IGNORECASE)
                if match:
                    key = match.group(0)
                    
                    category = self._categorize_secret(key)
                    risk = self._assess_risk(key, category)
                    
                    entry = SecretEntry(
                        name=key,
                        source='docker',
                        source_file=rel_path,
                        estimated_age_days=age,
                        category=category,
                        risk_level=risk
                    )
                    
                    self.secrets[f"docker:{key}:{i}"] = entry


class RotationAnalyzer:
    """Analyzes secrets for rotation needs."""
    
    def __init__(self, secrets: dict[str, SecretEntry], threshold_days: int = 90):
        self.secrets = secrets
        self.threshold_days = threshold_days
        self.reminders: list[RotationReminder] = []
        self.report = RotationReport(total_secrets_found=len(secrets))
    
    def analyze(self) -> tuple[list[RotationReminder], RotationReport]:
        """Analyze which secrets need rotation."""
        for secret in self.secrets.values():
            threshold = ROTATION_THRESHOLDS.get(secret.category, ROTATION_THRESHOLDS['default'])
            effective_threshold = min(threshold, self.threshold_days)
            
            days_old = secret.estimated_age_days
            
            if days_old > effective_threshold:
                exceeded_by = days_old - effective_threshold
                
                # Determine priority
                if exceeded_by > effective_threshold * 0.5:  # More than 50% over
                    priority = "IMMEDIATE"
                    self.report.immediate_action += 1
                elif exceeded_by > 0:
                    priority = "SOON"
                    self.report.soon_needed += 1
                else:
                    priority = "SCHEDULED"
                
                recommendation = self._generate_recommendation(secret, days_old, threshold)
                
                reminder = RotationReminder(
                    secret=secret,
                    days_since_rotation=days_old,
                    threshold_exceeded_by=exceeded_by,
                    priority=priority,
                    recommendation=recommendation
                )
                
                self.reminders.append(reminder)
                self.report.secrets_needing_rotation += 1
            else:
                self.report.well_managed += 1
            
            # Track by category
            self.report.by_category[secret.category] = self.report.by_category.get(secret.category, 0) + 1
            self.report.by_source[secret.source] = self.report.by_source.get(secret.source, 0) + 1
        
        # Sort reminders by urgency
        self.reminders.sort(key=lambda r: (
            {'IMMEDIATE': 0, 'SOON': 1, 'SCHEDULED': 2}.get(r.priority, 3),
            -r.days_since_rotation
        ))
        
        return self.reminders, self.report
    
    def _generate_recommendation(self, secret: SecretEntry, 
                                days_old: int, threshold: int) -> str:
        """Generate rotation recommendation."""
        base = f"Rotate '{secret.name}' ({secret.category})"
        
        if secret.risk_level == 'CRITICAL':
            base += " - This is a high-risk secret, rotate immediately."
        elif secret.risk_level == 'HIGH':
            base += " - High priority due to sensitivity."
        
        if secret.source != 'infisical':
            base += " Consider migrating to encrypted store like Infisical."
        
        # Category-specific advice
        if secret.category == 'payment':
            base += " Check with payment provider for any key rotation procedures."
        elif secret.category == 'database':
            base += " Plan downtime window for database credential rotation."
        elif secret.category == 'jwt':
            base += " Consider short-lived tokens with refresh token rotation."
        
        return base


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, reminders: list[RotationReminder], report: RotationReport,
                 secrets: dict[str, SecretEntry]):
        self.reminders = reminders
        self.report = report
        self.secrets = secrets
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI SECRET ROTATION REMINDER")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append(f"Rotation Threshold: {90} days")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Secrets Found:          {self.report.total_secrets_found}")
        lines.append(f"  Needing Rotation:             {self.report.secrets_needing_rotation}")
        lines.append(f"    🚨 Immediate Action:         {self.report.immediate_action}")
        lines.append(f"    ⚠️  Rotate Soon:              {self.report.soon_needed}")
        lines.append(f"    ✅ Within Safe Range:        {self.report.well_managed}")
        lines.append("")
        
        # By Risk Level
        lines.append("\nBY RISK LEVEL")
        lines.append("-" * 40)
        for risk in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = sum(1 for s in self.secrets.values() if s.risk_level == risk)
            if count:
                icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(risk, '')
                lines.append(f"  {icon} {risk:<12} {count:>5}")
        
        # Reminders
        if self.reminders:
            lines.append("\n\n🔄 ROTATION REMINDERS")
            lines.append("=" * 40)
            
            for i, reminder in enumerate(self.reminders[:25], 1):
                priority_icon = {'IMMEDIATE': '🚨', 'SOON': '⚠️', 'SCHEDULED': '📅'}.get(reminder.priority, '')
                secret = reminder.secret
                
                lines.append(f"\n  {i}. {priority_icon} [{reminder.priority}] {secret.name}")
                lines.append(f"     Category:   {secret.category}")
                lines.append(f"     Source:     {secret.source} ({secret.source_file})")
                lines.append(f"     Age:       ~{reminder.days_since_rotation} days")
                lines.append(f"     Over by:   {reminder.threshold_exceeded_by} days")
                lines.append(f"     💡 {reminder.recommendation}")
            
            if len(self.reminders) > 25:
                lines.append(f"\n  ... and {len(self.reminders) - 25} more reminders")
        
        # All Secrets Overview
        lines.append("\n\n📋 ALL SECRETS BY SOURCE")
        lines.append("-" * 40)
        
        by_source = defaultdict(list)
        for secret in self.secrets.values():
            by_source[secret.source].append(secret)
        
        for source, secrets_in_source in sorted(by_source.items()):
            lines.append(f"\n  {source}: ({len(secrets_in_source)} secrets)")
            for secret in sorted(secrets_in_source, key=lambda s: s.name)[:10]:
                age_str = f"{secret.estimated_age_days}d old" if secret.estimated_age_days else "?"
                lines.append(f"    • [{secret.risk_level}] {secret.name} ({secret.category}) - {age_str}")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("BEST PRACTICES FOR SECRET MANAGEMENT")
        lines.append("=" * 80)
        lines.append("""
1. **Use a Secret Manager**
   - Infisical, HashiCorp Vault, AWS Secrets Manager
   - Never commit secrets to code

2. **Automate Rotation**
   - Set up automated rotation schedules
   - Use short-lived credentials where possible
   - Implement zero-downtime rotation

3. **Monitor Age**
   - Add this script to CI/CD pipeline
   - Set alerts for secrets approaching threshold
   - Document rotation procedures

4. **Access Control**
   - Limit who can view/create secrets
   - Audit access logs
   - Use principle of least privilege

5. **Emergency Procedures**
   - Have incident response plan ready
   - Know how to quickly rotate compromised secrets
   - Test rotation procedures regularly
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": asdict(self.report),
            "reminders": [{
                "secret_name": r.secret.name,
                "category": r.secret.category,
                "risk_level": r.secret.risk_level,
                "source": r.secret.source,
                "days_old": r.days_since_rotation,
                "threshold_exceeded_by": r.threshold_exceeded_by,
                "priority": r.priority,
                "recommendation": r.recommendation
            } for r in self.reminders],
            "all_secrets": [{
                "name": s.name,
                "category": s.category,
                "risk_level": s.risk_level,
                "source": s.source,
                "estimated_age_days": s.estimated_age_days
            } for s in self.secrets.values()],
            "thresholds": ROTATION_THRESHOLDS,
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Secret Rotation Reminder',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--project-root', '-p', default='..')
    parser.add_argument('--threshold-days', '-t', type=int, default=90,
                       help='Rotation threshold in days (default: 90)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-immediate', action='store_true',
                       help='Exit error if immediate action needed')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    project_root = (script_dir / args.project_root).resolve()
    
    print("🔐 SupremeAI Secret Rotation Reminder")
    print(f"   Project Root: {project_root}")
    print(f"   Threshold: {args.threshold_days} days")
    print()
    
    # Scan for secrets
    scanner = SecretScanner(project_root)
    secrets = scanner.scan()
    
    # Analyze rotation needs
    analyzer = RotationAnalyzer(secrets, args.threshold_days)
    reminders, report = analyzer.analyze()
    
    # Generate report
    generator = ReportGenerator(reminders, report, secrets)
    
    if args.output_format == 'json':
        output = json.dumps(generator.generate_json_report(), indent=2)
    else:
        output = generator.generate_text_report()
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"✅ Report written to: {args.output_file}")
    else:
        print(output)
    
    # Exit code
    if args.fail_on_immediate and report.immediate_action > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
