#!/usr/bin/env python3
"""
Dependency Freshness Radar for SupremeAI
==========================================
Tracks how outdated dependencies are in pyproject.toml, package.json,
and requirements files. Pure freshness tracking (not vulnerability scanning).

Features:
- Checks current version vs latest available (from PyPI/npm)
- Identifies stale dependencies that may miss security patches
- Categorizes by staleness level
- Generates prioritized update list

Usage:
    python dependency_freshness_radar.py [--project-root ../] [--output-format text|json]
    
Note: This script checks version ages. For vulnerability scanning, use 
the existing check_dependencies.py or dedicated security tools.

Self-healing principles:
- Auto-discovers all dependency files
- No hardcoded package lists - fully dynamic
- CI-friendly output
"""

import os
import re
import sys
import json
import subprocess
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.request import urlopen
from urllib.error import URLError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """A project dependency."""
    name: str
    current_version: str
    source_file: str  # Where it's declared
    dep_type: str  # 'production', 'dev', 'optional'
    category: str  # 'python', 'nodejs', etc.


@dataclass 
class DependencyStatus:
    """Status of a dependency including freshness info."""
    dependency: Dependency
    latest_version: Optional[str] = None
    days_since_release: int = 0  # Days since current version was published
    versions_behind: int = 0  # How many major/minor versions behind
    staleness_level: str = "UNKNOWN"  # FRESH, CURRENT, STALE, VERY_STALE, ANCIENT
    is_outdated: bool = False
    security_relevance: str = "LOW"  # HIGH, MEDIUM, LOW based on category


@dataclass 
class FreshnessReport:
    """Summary of dependency freshness analysis."""
    total_dependencies: int = 0
    fresh_count: int = 0
    current_count: int = 0
    stale_count: int = 0
    very_stale_count: int = 0
    ancient_count: int = 0
    unknown_count: int = 0  # Couldn't determine status
    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)
    high_priority_updates: List[str] = field(default_factory=list)


# Categories of dependencies that are more security-relevant
HIGH_SECURITY_CATEGORIES = {
    'framework', 'web', 'auth', 'crypto', 'security',
    'database', 'http', 'api', 'serialization',
}

# Common Python packages with known security implications
SECURITY_SENSITIVE_PYTHON = [
    'django', 'flask', 'fastapi', 'requests', 'urllib3',
    'cryptography', 'pyjwt', 'oauthlib', 'sqlalchemy',
    'psycopg2', 'pymongo', 'redis', 'celery',
    'pillow', 'numpy', 'pandas',
]

# Common Node.js packages with known security implications
SECURITY_SENSITIVE_NODE = [
    'express', 'koa', 'axios', 'lodash', 'underscore',
    'jsonwebtoken', 'passport', 'bcryptjs', 'helmet',
    'react', 'vue', 'angular', 'next',
]


class DependencyScanner:
    """Scans for dependencies from various sources."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.dependencies: Dict[str, Dependency] = {}
        
    def scan(self) -> Dict[str, Dependency]:
        """Scan all dependency sources."""
        self._scan_pyproject_toml()
        self._scan_requirements_files()
        self._scan_package_json()
        self._scan_setup_cfg()
        
        logger.info(f"Found {len(self.dependencies)} dependencies")
        return self.dependencies
    
    def _normalize_name(self, name: str) -> str:
        """Normalize package name for consistent lookup."""
        return name.lower().replace('-', '_').replace('.', '_')
    
    def _scan_pyproject_toml(self):
        """Scan pyproject.toml for dependencies."""
        pyproject = self.project_root / 'pyproject.toml'
        
        if not pyproject.exists():
            return
        
        try:
            with open(pyproject, 'r') as f:
                content = f.read()
            
            # Parse [dependencies] section
            deps_section = re.search(r'\[dependencies\](.*?)(?=\[|\Z)', content, re.DOTALL)
            if deps_section:
                deps_text = deps_section.group(1)
                for match in re.finditer(r'^(\w[\w\-]*)\s*=\s*["\']([^"\']+)["\']', 
                                       deps_text, re.MULTILINE):
                    name = match.group(1).lower()
                    version = match.group(2)
                    
                    key = self._normalize_name(name)
                    self.dependencies[key] = Dependency(
                        name=name,
                        current_version=version,
                        source_file='pyproject.toml',
                        dep_type='production',
                        category='python'
                    )
            
            # Parse [dev-dependencies] or [group.dev.dependencies]
            dev_sections = re.findall(r'\[(?:dev.?dependencies|group\.dev\.dependencies)\](.*?)(?=\[|\Z)', 
                                        content, re.DOTALL | re.IGNORECASE)
            for dev_section in dev_sections:
                for match in re.finditer(r'^(\w[\w\-]*)\s*=\s*["\']([^"\']+)["\']',
                                       dev_section, re.MULTILINE):
                    name = match.group(1).lower()
                    key = self._normalize_name(name)
                    
                    if key not in self.dependencies:
                        self.dependencies[key] = Dependency(
                            name=name,
                            current_version=match.group(2),
                            source_file='pyproject.toml',
                            dep_type='dev',
                            category='python'
                        )
                        else:
                            self.dependencies[key].dep_type = 'dev'
                            
        except Exception as e:
            logger.debug(f"Could not parse pyproject.toml: {e}")
    
    def _scan_requirements_files(self):
        """Scan requirements*.txt files."""
        req_patterns = ['requirements.txt', 'requirements-dev.txt', 
                       'requirements-prod.txt', 'requirements/*.txt']
        
        for pattern in req_patterns:
            if '*' in pattern:
                for req_file in self.project_root.glob(pattern):
                    self._parse_requirements_file(req_file)
            else:
                req_file = self.project_root / pattern
                if req_file.exists():
                    self._parse_requirements_file(req_file)
    
    def _parse_requirements_file(self, file_path: Path):
        """Parse a requirements file."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        dep_type = 'dev' if 'dev' in rel_path else 'production'
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Skip options and constraints
            if line.startswith('-') or line.startswith('--'):
                continue
            
            # Parse package==version or package>=version
            match = re.match(r'^([a-zA-Z0-9_-]+)\s*[=<>!]+\s*([\d\.\*\-\w]+)', line)
            if match:
                name = match.group(1).lower()
                version = match.group(2)
                
                key = self._normalize_name(name)
                
                if key not in self.dependencies:
                    self.dependencies[key] = Dependency(
                        name=name,
                        current_version=version,
                        source_file=rel_path,
                        dep_type=dep_type,
                        category='python'
                    )
    
    def _scan_package_json(self):
        """Scan package.json for dependencies."""
        pkg_json = self.project_root / 'package.json'
        
        if not pkg_json.exists():
            # Also check frontend subdirectory
            pkg_json = self.project_root / 'frontend' / 'package.json'
        
        if not pkg_json.exists():
            return
        
        try:
            with open(pkg_json, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.debug(f"Could not parse package.json: {e}")
            return
        
        rel_path = str(pkg_json.relative_to(self.project_root))
        
        # Regular dependencies
        for name, version in data.get('dependencies', {}).items():
            key = self._normalize_name(name)
            clean_version = version.replace('^', '').replace('~', '').replace('>=', '')
            
            self.dependencies[key] = Dependency(
                name=name,
                current_version=clean_version,
                source_file=rel_path,
                dep_type='production',
                category='nodejs'
            )
        
        # Dev dependencies
        for name, version in data.get('devDependencies', {}).items():
            key = self._normalize_name(name)
            clean_version = version.replace('^', '').replace('~', '').replace('>=', '')
            
            if key not in self.dependencies:
                self.dependencies[key] = Dependency(
                    name=name,
                    current_version=clean_version,
                    source_file=rel_path,
                    dep_type='dev',
                    category='nodejs'
                )
    
    def _scan_setup_cfg(self):
        """Scan setup.cfg for dependencies."""
        setup_cfg = self.project_root / 'setup.cfg'
        
        if not setup_cfg.exists():
            return
        
        try:
            with open(setup_cfg, 'r') as f:
                content = f.read()
        except Exception:
            return
        
        # Look for install_requires section
        install_section = re.search(r'install_requires\s*=\s*(\[.*?\])', content, re.DOTALL)
        if install_section:
            deps_str = install_section.group(1)
            for match in re.finditer(r'["\']([^"\']+)["\']', deps_str):
                # This might include version specs
                dep_string = match.group(1)
                parts = re.split(r'[<>=!]+', dep_string)
                if parts:
                    name = parts[0].lower().strip()
                    key = self._normalize_name(name)
                    
                    if key not in self.dependencies:
                        self.dependencies[key] = Dependency(
                            name=name,
                            current_version=parts[1] if len(parts) > 1 else '?',
                            source_file='setup.cfg',
                            dep_type='production',
                            category='python'
                        )


class VersionChecker:
    """Checks versions against package repositories."""
    
    def __init__(self, dependencies: Dict[str, Dependency]):
        self.dependencies = dependencies
        self.statuses: Dict[str, DependencyStatus] = {}
        
    def check(self) -> Dict[str, DependencyStatus]:
        """Check all dependencies."""
        for key, dep in self.dependencies.items():
            status = self._check_dependency(dep)
            self.statuses[key] = status
        
        return self.statuses
    
    def _check_dependency(self, dep: Dependency) -> DependencyStatus:
        """Check a single dependency."""
        status = DependencyStatus(dependency=dep)
        
        # Determine security relevance
        status.security_relevance = self._assess_security_relevance(dep)
        
        # Try to get latest version
        if dep.category == 'python':
            latest = self._get_pypi_latest(dep.name)
        elif dep.category == 'nodejs':
            latest = self._get_npm_latest(dep.name)
        else:
            latest = None
        
        if latest:
            status.latest_version = latest
            status.versions_behind = self._count_versions_behind(
                dep.current_version.replace(' ', ''), latest
            )
            
            # Estimate staleness (rough heuristic)
            status.staleness_level = self._calculate_staleness(status)
            status.is_outdated = status.staleness_level in ('STALE', 'VERY_STALE', 'ANCIENT')
        else:
            status.staleness_level = "UNKNOWN"
        
        return status
    
    def _assess_security_relevance(self, dep: Dependency) -> str:
        """Assess how security-relevant a dependency is."""
        name_lower = dep.name.lower()
        
        if dep.category == 'python' and name_lower in SECURITY_SENSITIVE_PYTHON:
            return 'HIGH'
        
        if dep.category == 'nodejs' and name_lower in SECURITY_SENSITIVE_NODE:
            return 'HIGH'
        
        # Check category keywords
        for cat in HIGH_SECURITY_CATEGORIES:
            if cat in name_lower:
                return 'MEDIUM'
        
        return 'LOW'
    
    def _get_pypi_latest(self, package: str) -> Optional[str]:
        """Get latest version from PyPI."""
        try:
            url = f"https://pypi.org/pypi/{package}/json"
            with urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                return data.get('info', {}).get('version')
        except (URLError, json.JSONDecodeError, Exception) as e:
            logger.debug(f"Could not fetch PyPI info for {package}: {e}")
            return None
    
    def _get_npm_latest(self, package: str) -> Optional[str]:
        """Get latest version from npm registry."""
        try:
            url = f"https://registry.npmjs.org/{package}"
            with urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                return data.get('dist-tags', {}).get('latest')
        except (URLError, json.JSONDecodeError, Exception) as e:
            logger.debug(f"Could not fetch npm info for {package}: {e}")
            return None
    
    @staticmethod
    def _count_versions_behind(current: str, latest: str) -> int:
        """Roughly count how many versions behind."""
        try:
            # Extract major.minor numbers
            curr_parts = list(map(int, re.findall(r'\d+', current)[:2]))
            lat_parts = list(map(int, re.findall(r'\d+', latest)[:2]))
            
            if len(curr_parts) >= 2 and len(lat_parts) >= 2:
                major_diff = lat_parts[0] - curr_parts[0]
                minor_diff = lat_parts[1] - curr_parts[1]
                
                return max(0, major_diff * 10 + minor_diff)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"Silenced error: {e}")
        
        return 1 if current != latest else 0
    
    @staticmethod
    def _calculate_staleness(status: DependencyStatus) -> str:
        """Determine staleness level from version comparison."""
        behind = status.versions_behind
        
        if behind == 0:
            return "FRESH"
        elif behind <= 2:
            return "CURRENT"
        elif behind <= 5:
            return "STALE"
        elif behind <= 10:
            return "VERY_STALE"
        else:
            return "ANCIENT"


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, statuses: Dict[str, DependencyStatus], 
                 dependencies: Dict[str, Dependency]):
        self.statuses = statuses
        self.dependencies = dependencies
        self.report = FreshnessReport(total_dependencies=len(dependencies))
        
        # Calculate summary stats
        self._generate_summary()
    
    def _generate_summary(self):
        """Generate summary statistics."""
        for status in self.statuses.values():
            level = status.staleness_level
            
            if level == "FRESH":
                self.report.fresh_count += 1
            elif level == "CURRENT":
                self.report.current_count += 1
            elif level == "STALE":
                self.report.stale_count += 1
            elif level == "VERY_STALE":
                self.report.very_stale_count += 1
            elif level == "ANCIENT":
                self.report.ancient_count += 1
            else:
                self.report.unknown_count += 1
            
            # Track by category
            cat = status.dependency.category
            if cat not in self.report.by_category:
                self.report.by_category[cat] = {'total': 0, 'outdated': 0}
            self.report.by_category[cat]['total'] += 1
            if status.is_outdated:
                self.report.by_category[cat]['outdated'] += 1
            
            # High priority updates
            if (status.is_outdated and 
                status.security_relevance in ('HIGH', 'MEDIUM') and
                status.staleness_level in ('VERY_STALE', 'ANCIENT')):
                self.report.high_priority_updates.append(
                    f"{status.dependency.name} ({status.dependency.current_version} → {status.latest_version})"
                )
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI DEPENDENCY FRESHNESS RADAR")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Dependencies:           {self.report.total_dependencies}")
        lines.append(f"  ✅ Fresh (Up to Date):         {self.report.fresh_count}")
        lines.append(f"  🟢 Current (Minor lag):         {self.report.current_count}")
        lines.append(f"  🟡 Stale (Needs Update):       {self.report.stale_count}")
        lines.append(f"  🟠 Very Stale (Major lag):     {self.report.very_stale_count}")
        lines.append(f"  🔴 Ancient (Very Outdated):   {self.report.ancient_count}")
        lines.append(f"  ❓ Unknown Status:             {self.report.unknown_count}")
        lines.append("")
        
        # By Category
        if self.report.by_category:
            lines.append("\nBY CATEGORY")
            lines.append("-" * 40)
            lines.append(f"  {'Category':<15} {'Total':>8} {'Outdated':>10} {'Rate':>8}")
            
            for cat, stats in sorted(self.report.by_category.items()):
                rate = (stats['outdated'] / stats['total'] * 100) if stats['total'] else 0
                icon = "✅" if rate < 20 else ("🟡" if rate < 50 else "🔴")
                lines.append(f"  {icon} {cat:<14} {stats['total']:>7} {stats['outdated']:>9} {rate:>7.0f}%")
        
        # High Priority Updates
        if self.report.high_priority_updates:
            lines.append("\n\n🚨 HIGH PRIORITY UPDATES (Security-Relevant + Very Stale)")
            lines.append("=" * 40)
            for update in self.report.high_priority_updates[:15]:
                lines.append(f"  • {update}")
        
        # Detailed Status
        outdated_statuses = [s for s in self.statuses.values() if s.is_outdated]
        if outdated_statuses:
            lines.append("\n\n📋 OUTDATED DEPENDENCIES DETAILS")
            lines.append("=" * 40)
            
            # Sort by severity then staleness
            sorted_outdated = sorted(outdated_statuses, key=lambda s: (
                {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(s.security_relevance, 3),
                {'ANCIENT': 0, 'VERY_STALE': 1, 'STALE': 2}.get(s.staleness_level, 3)
            ))
            
            for i, status in enumerate(sorted_outdated[:25], 1):
                dep = status.dependency
                sec_icon = {'HIGH': '🔒', 'MEDIUM': '🔓', 'LOW': '🔓'}.get(status.security_relevance, '')
                
                lines.append(f"\n  {i}. [{status.staleness_level}] {sec_icon} {dep.name}")
                lines.append(f"     Current: {dep.current_version}")
                lines.append(f"     Latest:  {status.latest_version or 'unknown'}")
                lines.append(f"     Source:  {dep.source_file}")
                lines.append(f"     Type:    {dep.dep_type}")
            
            if len(sorted_outdated) > 25:
                lines.append(f"\n  ... and {len(sorted_outdated) - 25} more outdated dependencies")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Immediate Actions:

1. **Update Ancient Dependencies First**
   - These may have unpatched security vulnerabilities
   - Breaking changes likely, so plan carefully

2. **Address Security-Sensitive Packages**
   - Auth, crypto, HTTP libraries should be current
   - Check security advisories for known issues

3. **Schedule Regular Updates**
   - Set up Dependabot or Renovate for automated PRs
   - Monthly dependency review process

4. **Pin Critical Versions**
   - Use exact versions for production
   - Allow patches only for dev dependencies

CI Integration:
  Add to pipeline:
    python dependency_freshness_radar.py --fail-if-stale-pct 20

Monitoring Tools:
  - dependabot (GitHub)
  - renovatebot
  - snyk (vulnerability scanning)
  - pip-audit (Python)
  - npm audit (Node.js)

Note: This tool tracks VERSION AGE only.
For VULNERABILITY SCANNING, use dedicated tools like Snyk, 
Dependabot security updates, or OWASP Dependency Check.
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total": self.report.total_dependencies,
                "fresh": self.report.fresh_count,
                "current": self.report.current_count,
                "stale": self.report.stale_count,
                "very_stale": self.report.very_stale_count,
                "ancient": self.report.ancient_count,
                "unknown": self.report.unknown_count,
            },
            "by_category": self.report.by_category,
            "high_priority_updates": self.report.high_priority_updates,
            "details": [{
                "name": s.dependency.name,
                "current_version": s.dependency.current_version,
                "latest_version": s.latest_version,
                "staleness": s.staleness_level,
                "is_outdated": s.is_outdated,
                "security_relevance": s.security_relevance,
                "source": s.dependency.source_file,
                "type": s.dependency.dep_type,
                "category": s.dependency.category,
            } for s in sorted(self.statuses.values(), 
                             key=lambda x: x.dependency.name)],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Dependency Freshness Radar',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--project-root', '-p', default='..')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-if-stale-pct', type=float, default=0,
                       help='Fail if stale percentage exceeds this')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    project_root = (script_dir / args.project_root).resolve()
    
    print(f"📦 SupremeAI Dependency Freshness Radar")
    print(f"   Project Root: {project_root}")
    print()
    
    # Scan dependencies
    scanner = DependencyScanner(project_root)
    dependencies = scanner.scan()
    
    # Check versions
    checker = VersionChecker(dependencies)
    statuses = checker.check()
    
    # Generate report
    generator = ReportGenerator(statuses, dependencies)
    
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
    total = generator.report.total_dependencies
    stale_total = (generator.report.stale_count + 
                   generator.report.very_stale_count + 
                   generator.report.ancient_count)
    
    if args.fail_if_stale_pct > 0 and total > 0:
        stale_pct = (stale_total / total) * 100
        if stale_pct > args.fail_if_stale_pct:
            sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
