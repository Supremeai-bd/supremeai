#!/usr/bin/env python3
"""
Environment Variable Reconciler for SupremeAI
==============================================
Finds all env var usage in code (os.getenv, settings.X, os.environ)
and cross-references with declared vars in render.yaml, Infisical config,
.env files, and docker-compose.yml.

Flags:
- Vars used in code but not declared anywhere (runtime error risk)
- Vars declared but never used in code (dead config)
- Vars with inconsistent default values

Usage:
    python env_var_reconciler.py [--project-root ../] [--output-format json|text]
    
Self-healing principles:
- Auto-discovers all config sources
- No hardcoded var names - fully dynamic
- CI-friendly exit codes for missing critical vars
"""

import os
import re
import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
from datetime import datetime
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EnvVarUsage:
    """Represents a single environment variable usage in code."""
    name: str
    file_path: str
    line_number: int
    usage_type: str  # getenv, environ, settings, os.environ.get, etc.
    has_default: bool = False
    default_value: Optional[str] = None
    context: str = ""  # Surrounding code context


@dataclass
class EnvVarDeclaration:
    """Represents an environment variable declaration in config."""
    name: str
    source: str  # render.yaml, .env, docker-compose, infisical, etc.
    source_file: str
    value_or_default: Optional[str] = None
    is_required: bool = False
    description: str = ""


@dataclass
class ReconciliationIssue:
    """Represents a reconciliation issue."""
    severity: str  # CRITICAL, WARNING, INFO
    issue_type: str
    var_name: str
    description: str
    usages: List[EnvVarUsage] = field(default_factory=list)
    declarations: List[EnvVarDeclaration] = field(default_factory=list)
    suggestion: str = ""


class CodeEnvVarExtractor:
    """Extracts environment variable usage from source code."""
    
    # Patterns for different languages/frameworks
    PYTHON_PATTERNS = [
        # os.getenv("VAR") or os.getenv('VAR')
        (r'os\.getenv\s*\(\s*["\']([^"\']+)["\']', 'os.getenv'),
        (r'os\.getenv\s*\(\s*["\']([^"\']+)["\']\s*,\s*([^)]+)\)', 'os.getenv_with_default'),
        # os.environ["VAR"] or os.environ['VAR']
        (r"os\.environ\[\"([^\"]+)\"\]", 'os.environ_bracket'),
        (r"os\.environ\['([^']+)'\]", 'os.environ_bracket'),
        # os.environ.get("VAR")
        (r'os\.environ\.get\s*\(\s*["\']([^"\']+)["\']', 'os.environ_get'),
        (r'os\.environ\.get\s*\(\s*["\']([^"\']+)["\']\s*,\s*([^)]+)\)', 'os.environ_get_default'),
        # settings.VAR or settings.get("VAR")
        (r'settings\.(\w+)', 'settings_attr'),
        (r'settings\.get\s*\(\s*["\']([^"\']+)["\']', 'settings_get'),
        # os.environ["VAR"] alternative patterns
        (r'environ\.get\s*\(\s*["\']([^"\']+)["\']', 'environ_get'),
        # Direct access pattern
        (r'(?:ENV|CONFIG|SETTINGS)\[["\']([^"\']+)["\']\]', 'config_dict'),
        # Pydantic BaseSettings / env_list
        (r'model_config\s*=\s*[^{]*\{[^}]*env_prefix\s*=\s*["\']([^"\']*)["\']', 'pydantic_prefix'),
    ]
    
    TYPESCRIPT_PATTERNS = [
        # process.env.VAR
        (r'process\.env\.(\w+)', 'process_env'),
        # process.env["VAR"]
        (r'process\.env\[["\']([^"\']+)["\']\]', 'process_env_bracket'),
        # import.meta.env.VAR (Vite)
        (r'import\.meta\.env\.(\w+)', 'vite_meta_env'),
    ]
    
    SHELL_PATTERNS = [
        # $VAR or ${VAR}
        (r'\$\{?(\w+)\}?', 'shell_var'),
        # export VAR=
        (r'^export\s+(\w+)=', 'export_statement'),
    ]
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.usages: List[EnvVarUsage] = []
        
    def extract_all(self) -> List[EnvVarUsage]:
        """Extract all env var usages from all source files."""
        self._extract_from_python()
        self._extract_from_typescript()
        self._extract_from_shell()
        self._extract_from_yaml_configs()
        
        logger.info(f"Found {len(self.usages)} environment variable usages")
        return self.usages
    
    def _extract_from_python(self):
        """Extract from Python files."""
        py_files = list(self.project_root.rglob("*.py"))
        # Skip common non-source directories
        skip_dirs = {'__pycache__', '.git', 'node_modules', 'venv', '.venv', 
                    'migrations', 'dist', 'build', '.tox'}
        
        for py_file in py_files:
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            self._extract_py_file(py_file)
    
    def _extract_py_file(self, file_path: Path):
        """Extract env vars from a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        for i, line in enumerate(lines):
            # Skip comments and strings (basic check)
            if line.strip().startswith('#'):
                continue
                
            for pattern, usage_type in self.PYTHON_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    var_name = match.group(1)
                    
                    # Skip if it looks like a normal string (not env var)
                    if not var_name.isupper() and usage_type != 'settings_attr':
                        if not any(c.isupper() for c in var_name):
                            continue
                    
                    # Check for default value
                    has_default = False
                    default_val = None
                    if len(match.groups()) > 1 and match.group(2):
                        has_default = True
                        default_val = match.group(2).strip().strip('"\'')
                    
                    # Get context (surrounding line)
                    context = line.strip()[:100]
                    
                    self.usages.append(EnvVarUsage(
                        name=var_name.upper() if var_name.isupper() else var_name,
                        file_path=rel_path,
                        line_number=i + 1,
                        usage_type=usage_type,
                        has_default=has_default,
                        default_value=default_val,
                        context=context
                    ))
    
    def _extract_from_typescript(self):
        """Extract from TypeScript/JavaScript files."""
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        skip_dirs = {'node_modules', 'dist', '.next', 'coverage', '__pycache__'}
        
        for ext in extensions:
            for ts_file in self.project_root.rglob(ext):
                if any(skip in str(ts_file) for skip in skip_dirs):
                    continue
                self._extract_ts_file(ts_file)
    
    def _extract_ts_file(self, file_path: Path):
        """Extract env vars from TypeScript/JavaScript file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        for i, line in enumerate(lines):
            if line.strip().startswith('//') or line.strip().startswith('*'):
                continue
                
            for pattern, usage_type in self.TYPESCRIPT_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    var_name = match.group(1)
                    context = line.strip()[:100]
                    
                    self.usages.append(EnvVarUsage(
                        name=var_name,
                        file_path=rel_path,
                        line_number=i + 1,
                        usage_type=usage_type,
                        context=context
                    ))
    
    def _extract_from_shell(self):
        """Extract from shell scripts."""
        shell_extensions = ['*.sh', '*.bash', '*.zsh']
        
        for ext in shell_extensions:
            for sh_file in self.project_root.rglob(ext):
                if '__pycache__' in str(sh_file) or 'node_modules' in str(sh_file):
                    continue
                self._extract_sh_file(sh_file)
    
    def _extract_sh_file(self, file_path: Path):
        """Extract env vars from shell script."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return
            
        rel_path = str(file_path.relative_to(self.project_root))
        
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                continue
                
            for pattern, usage_type in self.SHELL_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    var_name = match.group(1)
                    # Filter out shell variables that aren't env vars
                    if var_name.isupper() or (i > 0 and 'export' in lines[i-1]):
                        self.usages.append(EnvVarUsage(
                            name=var_name,
                            file_path=rel_path,
                            line_number=i + 1,
                            usage_type=usage_type,
                            context=line.strip()[:100]
                        ))
    
    def _extract_from_yaml_configs(self):
        """Extract env var references from YAML configs (docker-compose, etc.)."""
        yaml_files = ['docker-compose.yml', 'docker-compose.yaml', 
                     'render.yaml', '.github/workflows/*.yml']
        
        for pattern in yaml_files:
            for yaml_file in self.project_root.glob(pattern):
                self._extract_yaml_file(yaml_file)
    
    def _extract_yaml_file(self, file_path: Path):
        """Extract env var references from YAML."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return
        
        # Find ${VAR_NAME} patterns
        rel_path = str(file_path.relative_to(self.project_root))
        matches = re.finditer(r'\$\{(\w+)\}', content)
        
        for match in matches:
            self.usages.append(EnvVarUsage(
                name=match.group(1),
                file_path=rel_path,
                line_number=0,  # YAML doesn't give us easy line numbers here
                usage_type='yaml_interpolation',
                context=f"YAML interpolation in {rel_path}"
            ))


class ConfigDeclarationExtractor:
    """Extracts env var declarations from configuration files."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.declarations: List[EnvVarDeclaration] = []
        
    def extract_all(self) -> List[EnvVarDeclaration]:
        """Extract declarations from all config sources."""
        self._extract_from_render_yaml()
        self._extract_from_dotenv()
        self._extract_from_docker_compose()
        self._extract_from_infisical()
        self._extract_from_github_secrets()
        
        logger.info(f"Found {len(self.declarations)} environment variable declarations")
        return self.declarations
    
    def _extract_from_render_yaml(self):
        """Extract from render.yaml"""
        render_yaml = self.project_root / 'render.yaml'
        if not render_yaml.exists():
            return
            
        try:
            with open(render_yaml, 'r') as f:
                content = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not parse render.yaml: {e}")
            return
        
        services = content.get('services', [])
        if isinstance(services, dict):
            services = [services]
            
        for service in services:
            env_vars = service.get('envVars', [])
            for env_var in env_vars:
                if isinstance(env_var, dict):
                    key = env_var.get('key', '')
                    self.declarations.append(EnvVarDeclaration(
                        name=key,
                        source='render.yaml',
                        source_file='render.yaml',
                        value_or_default=env_var.get('value'),
                        is_required=True  # Render vars are typically required
                    ))
    
    def _extract_from_dotenv(self):
        """Extract from .env files"""
        dotenv_patterns = ['.env', '.env.local', '.env.production', '.env.development']
        
        for pattern in dotenv_patterns:
            dotenv_file = self.project_root / pattern
            if dotenv_file.exists():
                self._parse_dotenv(dotenv_file, pattern)
    
    def _parse_dotenv(self, file_path: Path, source_name: str):
        """Parse a .env file."""
        try:
            with open(file_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Handle KEY=VALUE or KEY="VALUE" or KEY='VALUE'
                    match = re.match(r'^(\w+)\s*=\s*(.*)$', line)
                    if match:
                        key = match.group(1)
                        value = match.group(2).strip().strip('"\'')
                        
                        self.declarations.append(EnvVarDeclaration(
                            name=key,
                            source=source_name,
                            source_file=str(file_path),
                            value_or_default=value if value else None
                        ))
        except Exception as e:
            logger.debug(f"Could not parse {file_path}: {e}")
    
    def _extract_from_docker_compose(self):
        """Extract from docker-compose.yml"""
        dc_patterns = ['docker-compose.yml', 'docker-compose.yaml']
        
        for pattern in dc_patterns:
            dc_file = self.project_root / pattern
            if dc_file.exists():
                self._parse_docker_compose(dc_file)
    
    def _parse_docker_compose(self, file_path: Path):
        """Parse docker-compose for environment declarations."""
        try:
            with open(file_path, 'r') as f:
                content = yaml.safe_load(f)
        except Exception:
            return
        
        services = content.get('services', {})
        for service_name, service_config in services.items():
            # environment as list
            env_list = service_config.get('environment', [])
            if isinstance(env_list, list):
                for item in env_list:
                    if isinstance(item, str) and '=' in item:
                        key = item.split('=')[0].strip()
                        self.declarations.append(EnvVarDeclaration(
                            name=key,
                            source='docker-compose.yml',
                            source_file=str(file_path),
                            is_required=True
                        ))
            
            # env_file reference
            env_file = service_config.get('env_file', [])
            if isinstance(env_file, str):
                env_file = [env_file]
            for ef in env_file:
                ef_path = self.project_root / ef
                if ef_path.exists():
                    self._parse_dotenv(ef_path, f'docker-compose:{ef}')
    
    def _extract_from_infisical(self):
        """Extract from Infisical config files."""
        infisical_patterns = ['infisical.json', '.infisical.yaml', 'secrets_registry.yaml']
        
        for pattern in infisical_patterns:
            inf_file = self.project_root / pattern
            if inf_file.exists():
                self._parse_infisical(inf_file)
    
    def _parse_infisical(self, file_path: Path):
        """Parse Infisical/secrets registry."""
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix == '.json':
                    content = json.load(f)
                else:
                    content = yaml.safe_load(f)
        except Exception:
            return
        
        # Try to extract secrets from various formats
        if isinstance(content, dict):
            # Look for keys like 'secrets', 'environment', etc.
            for section in ['secrets', 'environment', 'variables']:
                items = content.get(section, {})
                if isinstance(items, dict):
                    for key, val in items.items():
                        self.declarations.append(EnvVarDeclaration(
                            name=key,
                            source=file_path.name,
                            source_file=str(file_path),
                            is_required=True
                        ))
                elif isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            key = item.get('key', item.get('name', ''))
                            if key:
                                self.declarations.append(EnvVarDeclaration(
                                    name=key,
                                    source=file_path.name,
                                    source_file=str(file_path),
                                    is_required=item.get('required', True)
                                ))
    
    def _extract_from_github_secrets(self):
        """Extract from GitHub Actions workflow references."""
        workflows_dir = self.project_root / '.github' / 'workflows'
        if not workflows_dir.exists():
            return
        
        for workflow_file in workflows_dir.glob('*.yml'):
            try:
                with open(workflow_file, 'r') as f:
                    content = yaml.safe_load(f)
                
                # Find env: sections and ${{ secrets.X }} references
                content_str = yaml.dump(content) if content else ""
                matches = re.finditer(r'secrets\.(\w+)', content_str)
                for match in matches:
                    self.declarations.append(EnvVarDeclaration(
                        name=match.group(1),
                        source='github-secrets',
                        source_file=str(workflow_file.relative_to(self.project_root)),
                        is_required=True
                    ))
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f"Silenced error: {e}")


class EnvVarReconciler:
    """Main reconciler that finds discrepancies between usage and declaration."""
    
    # Common vars that are often used but may be system-provided
    SYSTEM_VARS = {
        'PATH', 'HOME', 'USER', 'SHELL', 'LANG', 'TERM', 'PWD', 'OLDPWD',
        'HOSTNAME', 'LOGNAME', 'MAIL', 'EDITOR', 'PAGER', 'BROWSER',
        'PYTHONPATH', 'NODE_ENV', 'CI', 'GITHUB_ACTIONS', 'RENDER'
    }
    
    # Vars that might be optional/feature-flagged
    OPTIONAL_VAR_PATTERNS = [
        '^FEATURE_.*', '^ENABLE_.*', '^DEBUG_.*', '^VERBOSE_.*',
        '^OPTIONAL_.*', '^EXPERIMENTAL_.*'
    ]
    
    def __init__(self, usages: List[EnvVarUsage], declarations: List[EnvVarDeclaration]):
        self.usages = usages
        self.declarations = declarations
        self.issues: List[ReconciliationIssue] = []
        
        # Build lookup structures
        self.usage_map: Dict[str, List[EnvVarUsage]] = defaultdict(list)
        for usage in usages:
            self.usage_map[usage.name.upper()].append(usage)
        
        self.declaration_map: Dict[str, List[EnvVarDeclaration]] = defaultdict(list)
        for decl in declarations:
            self.declaration_map[decl.name.upper()].append(decl)
    
    def reconcile(self) -> List[ReconciliationIssue]:
        """Perform reconciliation and find issues."""
        self._find_undeclared_usages()
        self._find_unused_declarations()
        self._find_default_inconsistencies()
        self._find_naming_convention_violations()
        
        return self.issues
    
    def _is_system_var(self, var_name: str) -> bool:
        """Check if this is a standard system variable."""
        return var_name.upper() in self.SYSTEM_VARS
    
    def _is_optional_var(self, var_name: str) -> bool:
        """Check if this looks like an optional/feature flag var."""
        return any(re.match(p, var_name, re.IGNORECASE) for p in self.OPTIONAL_VAR_PATTERNS)
    
    def _find_undeclared_usages(self):
        """Find vars used in code but not declared anywhere."""
        for var_name, usages in sorted(self.usage_map.items()):
            if var_name in self.declaration_map:
                continue
                
            if self._is_system_var(var_name):
                continue
            
            # Determine severity based on whether it has defaults
            has_default = any(u.has_default for u in usages)
            is_optional = self._is_optional_var(var_name)
            
            if not has_default and not is_optional:
                severity = 'CRITICAL'
            elif not has_default:
                severity = 'WARNING'
            else:
                severity = 'INFO'
            
            self.issues.append(ReconciliationIssue(
                severity=severity,
                issue_type='UNDECLARED_USAGE',
                var_name=var_name,
                description=f"Variable '{var_name}' is used in code but not declared in any config",
                usages=usages,
                suggestion=f"Add '{var_name}' to render.yaml, .env, or Infisical"
            ))
    
    def _find_unused_declarations(self):
        """Find vars declared but never used in code."""
        for var_name, decls in sorted(self.declaration_map.items()):
            if var_name in self.usage_map:
                continue
            
            if self._is_system_var(var_name):
                continue
            
            self.issues.append(ReconciliationIssue(
                severity='INFO',
                issue_type='UNUSED_DECLARATION',
                var_name=var_name,
                description=f"Variable '{var_name}' is declared but never used in code",
                declarations=decls,
                suggestion="Remove unused declaration or verify it's needed at runtime"
            ))
    
    def _find_default_inconsistencies(self):
        """Find cases where same var has different defaults in different places."""
        for var_name, usages in sorted(self.usage_map.items()):
            defaults = set()
            for u in usages:
                if u.has_default and u.default_value:
                    defaults.add(u.default_value)
            
            if len(defaults) > 1:
                self.issues.append(ReconciliationIssue(
                    severity='WARNING',
                    issue_type='INCONSISTENT_DEFAULTS',
                    var_name=var_name,
                    description=f"Variable '{var_name}' has different defaults: {defaults}",
                    usages=usages,
                    suggestion="Standardize default value across codebase"
                ))
    
    def _find_naming_convention_violations(self):
        """Find env vars that don't follow UPPER_CASE convention."""
        for var_name, usages in self.usage_map.items():
            if var_name != var_name.upper() and not var_name.startswith('_'):
                # Allow some exceptions
                allowed_patterns = ['url', 'uri', 'host', 'path']
                if not any(var_name.lower().endswith(p) for p in allowed_patterns):
                    self.issues.append(ReconciliationIssue(
                        severity='INFO',
                        issue_type='NAMING_CONVENTION',
                        var_name=var_name,
                        description=f"Variable '{var_name}' doesn't follow UPPER_CASE convention",
                        usages=[usages[0]],
                        suggestion=f"Rename to {var_name.upper()} for consistency"
                    ))


class ReportGenerator:
    """Generates reports in various formats."""
    
    def __init__(self, issues: List[ReconciliationIssue], 
                 usages: List[EnvVarUsage],
                 declarations: List[EnvVarDeclaration]):
        self.issues = issues
        self.usages = usages
        self.declarations = declarations
    
    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI ENVIRONMENT VARIABLE RECONCILIATION REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        critical = sum(1 for i in self.issues if i.severity == 'CRITICAL')
        warnings = sum(1 for i in self.issues if i.severity == 'WARNING')
        infos = sum(1 for i in self.issues if i.severity == 'INFO')
        
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Variables Used in Code:      {len(set(u.name for u in self.usages))}")
        lines.append(f"  Variables Declared:           {len(set(d.name for d in self.declarations))}")
        lines.append(f"  Critical Issues (Missing):    {critical}")
        lines.append(f"  Warnings:                    {warnings}")
        lines.append(f"  Info Notes:                  {infos}")
        lines.append("")
        
        # Group by type
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.issue_type].append(issue)
        
        # Detailed findings
        lines.append("DETAILED FINDINGS")
        lines.append("-" * 40)
        
        type_order = ['UNDECLARED_USAGE', 'UNUSED_DECLARATION', 
                     'INCONSISTENT_DEFAULTS', 'NAMING_CONVENTION']
        
        for issue_type in type_order:
            issues = by_type.get(issue_type, [])
            if not issues:
                continue
                
            type_labels = {
                'UNDECLARED_USAGE': '🔴 Used but NOT Declared',
                'UNUSED_DECLARATION': '🟢 Declared but NOT Used',
                'INCONSISTENT_DEFAULTS': '⚠️ Inconsistent Defaults',
                'NAMING_CONVENTION': '💡 Naming Convention'
            }
            
            lines.append(f"\n{type_labels.get(issue_type, issue_type)} ({len(issues)} issues)")
            lines.append("  " + "-" * 36)
            
            for i, issue in enumerate(issues[:30], 1):  # Limit output
                lines.append(f"\n  [{issue.severity}] {issue.var_name}")
                lines.append(f"     {issue.description}")
                
                if issue.usages:
                    lines.append(f"     Used in:")
                    for u in issue.usages[:3]:  # Show first 3 locations
                        lines.append(f"       - {u.file_path}:{u.line_number} ({u.usage_type})")
                    if len(issue.usages) > 3:
                        lines.append(f"       ... and {len(issue.usages) - 3} more locations")
                
                if issue.declarations:
                    lines.append(f"     Declared in:")
                    for d in issue.declarations[:3]:
                        lines.append(f"       - {d.source}:{d.source_file}")
                
                lines.append(f"     💡 {issue.suggestion}")
            
            if len(issues) > 30:
                lines.append(f"\n  ... and {len(issues) - 30} more issues of this type")
        
        # Quick fix commands
        lines.append("\n" + "=" * 80)
        lines.append("QUICK FIX COMMANDS")
        lines.append("=" * 80)
        
        undeclared = [i for i in self.issues if i.issue_type == 'UNDECLARED_USAGE' 
                     and i.severity == 'CRITICAL']
        if undeclared:
            lines.append("\n# Add these to your render.yaml or .env:")
            for issue in undeclared[:10]:
                lines.append(f"# {issue.var_name}=<value>")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate machine-readable JSON report."""
        return {
            "summary": {
                "unique_vars_used": len(set(u.name for u in self.usages)),
                "unique_vars_declared": len(set(d.name for d in self.declarations)),
                "critical_count": sum(1 for i in self.issues if i.severity == 'CRITICAL'),
                "warning_count": sum(1 for i in self.issues if i.severity == 'WARNING'),
                "info_count": sum(1 for i in self.issues if i.severity == 'INFO'),
            },
            "issues": [{
                "severity": i.severity,
                "type": i.issue_type,
                "var_name": i.var_name,
                "description": i.description,
                "suggestion": i.suggestion,
                "locations": [{"file": u.file_path, "line": u.line_number, "type": u.usage_type} 
                             for u in i.usages],
                "declarations": [{"source": d.source, "file": d.source_file} for d in i.declarations]
            } for i in self.issues],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Environment Variable Reconciler - Find mismatched env vars',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python env_var_reconciler.py
  python env_var_reconciler.py --project-root ./ --output-format json
  python env_var_reconciler.py --fail-on-critical  # For CI
"""
    )
    
    parser.add_argument('--project-root', '-p', default='..',
                       help='Project root directory (default: parent of scripts/)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text', help='Output format')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit with error code if critical issues found')
    parser.add_argument('--include-system-vars', action='store_true',
                       help='Include system variables in report')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Resolve path
    script_dir = Path(__file__).parent
    project_root = (script_dir / args.project_root).resolve()
    
    if not project_root.exists():
        logger.error(f"Project root not found: {project_root}")
        sys.exit(1)
    
    print(f"🔧 SupremeAI Environment Variable Reconciler")
    print(f"   Project Root: {project_root}")
    print()
    
    # Extract usages and declarations
    code_extractor = CodeEnvVarExtractor(project_root)
    usages = code_extractor.extract_all()
    
    config_extractor = ConfigDeclarationExtractor(project_root)
    declarations = config_extractor.extract_all()
    
    # Reconcile
    reconciler = EnvVarReconciler(usages, declarations)
    issues = reconciler.reconcile()
    
    # Generate report
    generator = ReportGenerator(issues, usages, declarations)
    
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
    
    # Exit code for CI
    critical_count = sum(1 for i in issues if i.severity == 'CRITICAL')
    if args.fail_on_critical and critical_count > 0:
        print(f"\n❌ Found {critical_count} critical issues!", file=sys.stderr)
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
