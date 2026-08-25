#!/usr/bin/env python3
"""
Agent Capability Registry Sync Checker for SupremeAI
======================================================
Detects when new Agent classes are defined but not registered in the
central capability registry. This prevents "agent fragmentation" where
new agents exist but aren't discoverable by the system.

Features:
- Finds all class definitions that inherit from Agent base classes
- Checks if they're registered in central registry/config
- Detects orphaned agents (defined but not registered)
- Validates registry entries point to existing agents

Usage:
    python agent_capability_registry_sync.py [--backend-dir ../backend] [--output-format text|json]
    
Self-healing principles:
- Auto-discovers Agent base classes and registry patterns
- No hardcoded agent list - fully dynamic
- CI-friendly: can fail build on unregistered agents
"""

import ast
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AgentDefinition:
    """An Agent class definition found in code."""
    name: str
    file_path: str
    line_number: int
    base_classes: List[str] = field(default_factory=list)
    is_abstract: bool = False
    docstring: str = ""
    module: str = ""  # Full module path
    has_run_method: bool = False  # Common interface indicator
    capabilities: List[str] = field(default_factory=list)  # Extracted from docstring/comments


@dataclass 
class RegistryEntry:
    """An entry in an agent registry/config."""
    name: str
    agent_class_ref: str  # Reference to agent class (e.g., "module.AgentClass")
    file_path: str
    line_number: int
    registry_type: str = ""  # 'dict', 'list', 'function_call', 'decorator'


@dataclass
class SyncIssue:
    """A synchronization issue between agents and registry."""
    issue_type: str  # 'UNREGISTERED_AGENT', 'BROKEN_REGISTRY_REF', 'MISSING_CAPABILITY', 'DUPLICATE_NAME'
    severity: str  # CRITICAL, WARNING, INFO
    agent_name: str
    description: str
    location: Optional[str] = None  # File:line of the issue
    registry_location: Optional[str] = None  # If applicable, where it should be registered
    suggestion: str = ""


# Patterns that suggest a class is an Agent
AGENT_BASE_CLASS_PATTERNS = {
    # Direct Agent base classes
    'Agent', 'BaseAgent', 'AbstractAgent', 'AgentBase',
    'AutonomousAgent', 'BaseAutonomousAgent',
    'AIAgent', 'LLMAgent',
    # SupremeAI specific
    'SentinelAgent', 'PerformanceGuardian', 'MorphicAdapter',
    'InsightMage', 'ChurnProphet', 'VulnerabilityProphet',
    'HeadlessTerminalAgent', 'InternetMonitorAgent',
    'SkillIngestor', 'SkillGC',
    'SyncGuardAgent', 'EvolutionAgent',
    # Framework-specific
    'CrewAIAgent', 'LangChainAgent', 'AutoGenAgent',
}

# Patterns that indicate a registry/registry-like structure
REGISTRY_PATTERNS = [
    r'(?:agent_?registry|agent_?map|agent_?dict|agents?\s*:\s*Dict)',
    r'(?:AGENT_?REGISTRY|AGENT_?MAP|ALL_?AGENTS)',
    r'(?:register_?agent|add_?agent)',
    r'@.*(?:register|agent_registry)',
]

# Files that are likely registries
REGISTRY_FILE_PATTERNS = [
    'registry', 'agent_registry', 'agents', 'catalog',
    'factory', 'agent_factory', 'registry_config',
]


class AgentScanner:
    """Scans for Agent class definitions."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.agents: Dict[str, AgentDefinition] = {}
        
    def scan(self) -> Dict[str, AgentDefinition]:
        """Scan for all Agent definitions."""
        py_files = self._find_python_files()
        
        for py_file in py_files:
            self._scan_file(py_file)
        
        logger.info(f"Found {len(self.agents)} Agent class definitions")
        return self.agents
    
    def _find_python_files(self) -> List[Path]:
        """Find Python files to scan."""
        skip_dirs = {
            '__pycache__', '.git', 'venv', '.venv', 'dist', 
            'build', '.tox', 'node_modules', '__pycache__',
            'tests', 'test', '__pycache__'
        }
        
        py_files = []
        for py_file in self.project_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
                
            # Focus on agents directory and nearby
            if any(p in str(py_file) for p in ['agents/', '/agents']):
                py_files.append(py_file)
            elif any(p in py_file.name.lower() for p in ['agent']):
                py_files.append(py_file)
        
        return py_files
    
    def _scan_file(self, file_path: Path):
        """Scan a single file for Agent definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            tree = ast.parse(content, filename=str(file_path))
            lines = content.split('\n')
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            return
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        module = rel_path.replace('/', '.').replace('.py', '')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if this looks like an Agent class
                base_names = [self._get_class_name(b) for b in node.bases]
                
                is_agent = any(
                    base in AGENT_BASE_CLASS_PATTERNS or 
                    'Agent' in base
                    for base in base_names
                )
                
                # Also check for naming convention
                is_agent = is_agent or node.name.endswith('Agent')
                
                if is_agent:
                    # Get docstring
                    docstring = ast.get_docstring(node) or ""
                    
                    # Check for abstract
                    is_abstract = any(
                        isinstance(item, ast.Assign) and
                        any(getattr(t, 'id', '') == '__abstract__' for t in getattr(item, 'targets', []))
                        for item in node.body
                    )
                    
                    # Check for run/execute method (common interface)
                    has_run = any(
                        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                        item.name in ('run', 'execute', 'process', 'act', 'perform', '__call__')
                        for item in node.body
                    )
                    
                    # Extract capabilities from docstring
                    capabilities = self._extract_capabilities(docstring)
                    
                    agent = AgentDefinition(
                        name=node.name,
                        file_path=rel_path,
                        line_number=node.lineno,
                        base_classes=base_names,
                        is_abstract=is_abstract,
                        docstring=docstring,
                        module=module,
                        has_run_method=has_run,
                        capabilities=capabilities
                    )
                    
                    # Use full module path as key for uniqueness
                    key = f"{module}.{node.name}"
                    self.agents[key] = agent
    
    def _get_class_name(self, node: ast.AST) -> str:
        """Get class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_class_name(node.value)
        return ""
    
    def _extract_capabilities(self, docstring: str) -> List[str]:
        """Extract capability keywords from docstring."""
        capabilities = []
        
        # Look for patterns like "Capabilities:", "Can:", etc.
        cap_patterns = [
            r'[Cc]apabilit(?:y|ies):\s*(.+)',
            r'[Cc]an\s+(?:be\s+used\s+to|be)\s*(.+)',
            r'[Pp]rovides?:\s*(.+)',
        ]
        
        for pattern in cap_patterns:
            match = re.search(pattern, docstring)
            if match:
                caps_text = match.group(1)
                # Split on commas and clean up
                for cap in re.split(r'[,;]', caps_text):
                    cap = cap.strip().lower()
                    if len(cap) > 2 and len(cap) < 50:
                        capabilities.append(cap)
        
        return capabilities[:5]  # Limit to top 5


class RegistryScanner:
    """Scans for agent registry definitions."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.entries: Dict[str, RegistryEntry] = {}  # agent_name -> RegistryEntry
        self.registry_files: List[str] = []
        
    def scan(self) -> Dict[str, RegistryEntry]:
        """Scan for all registry entries."""
        py_files = self._find_registry_files()
        
        for py_file in py_files:
            self._scan_file(py_file)
        
        logger.info(f"Found {len(self.entries)} registry entries in {len(self.registry_files)} files")
        return self.entries
    
    def _find_registry_files(self) -> List[Path]:
        """Find files that likely contain agent registries."""
        files = []
        
        # Check known patterns
        for pattern in REGISTRY_FILE_PATTERNS:
            files.extend(self.project_dir.rglob(f"*{pattern}*.py"))
        
        # Also check config files
        files.extend(self.project_dir.rglob("config/*.py"))
        files.extend(self.project_dir.rglob("*config*.py"))
        
        # Check JSON/YAML configs too
        files.extend(self.project_dir.rglob("agent_registry.json"))
        files.extend(self.project_dir.rglob("*registry*.yaml"))
        files.extend(self.project_dir.rglob("*registry*.yml"))
        
        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in files:
            f_str = str(f)
            if f_str not in seen and '__pycache__' not in f_str:
                seen.add(f_str)
                unique_files.append(f)
        
        return unique_files
    
    def _scan_file(self, file_path: Path):
        """Scan a single file for registry entries."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            # Try regex-based approach for non-Python files
            self._scan_with_regex(file_path)
            return
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        self.registry_files.append(rel_path)
        
        # Look for dictionary assignments that look like registries
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                self._check_assignment(node, lines, rel_path)
            
            elif isinstance(node, ast.Call):
                self._check_function_call(node, lines, rel_path)
    
    def _check_assignment(self, node: ast.Assign, lines: List[str], rel_path: str):
        """Check if assignment is a registry definition."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                
                # Check if this looks like a registry variable
                is_registry = any(
                    re.search(p, var_name, re.IGNORECASE)
                    for p in REGISTRY_PATTERNS[:3]
                ) or 'agent' in var_name.lower()
                
                if is_registry and isinstance(node.value, ast.Dict):
                    # This is a dict-based registry
                    for key, value in zip(node.value.keys, node.value.values):
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            agent_ref = self._get_agent_reference(value)
                            
                            entry = RegistryEntry(
                                name=key.value,
                                agent_class_ref=agent_ref,
                                file_path=rel_path,
                                line_number=node.lineno,
                                registry_type='dict'
                            )
                            self.entries[key.value] = entry
    
    def _check_function_call(self, node: ast.Call, lines: List[str], rel_path: str):
        """Check if function call is registering an agent."""
        func_name = self._get_call_name(node.func)
        
        if any(re.search(p, func_name, re.IGNORECASE) for p in REGISTRY_PATTERNS[2:]):
            # This might be a register_agent() call
            if node.args:
                first_arg = node.args[0]
                
                # Could be string name or class reference
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    agent_name = first_arg.value
                    agent_ref = self._get_agent_reference(node.args[1]) if len(node.args) > 1 else "?"
                    
                    entry = RegistryEntry(
                        name=agent_name,
                        agent_class_ref=agent_ref,
                        file_path=rel_path,
                        line_number=node.lineno,
                        registry_type='function_call'
                    )
                    self.entries[agent_name] = entry
    
    def _scan_with_regex(self, file_path: Path):
        """Use regex scanning for non-Python files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        
        # Simple pattern for JSON-like structures
        if file_path.suffix == '.json':
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, str):
                            self.entries[key] = RegistryEntry(
                                name=key,
                                agent_class_ref=value,
                                file_path=rel_path,
                                line_number=0,
                                registry_type='json'
                            )
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f"Silenced error: {e}")
    
    def _get_call_name(self, node: ast.AST) -> str:
        """Get function call name."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
    
    def _get_agent_reference(self, node: ast.AST) -> str:
        """Extract agent class reference from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_attr_chain(node)}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return "?"
    
    def _get_attr_chain(self, node: ast.Attribute) -> str:
        """Get full attribute chain."""
        parts = [node.attr]
        current = node.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))


class SyncChecker:
    """Checks synchronization between agents and registry."""
    
    def __init__(self, agents: Dict[str, AgentDefinition], 
                 registry: Dict[str, RegistryEntry]):
        self.agents = agents
        self.registry = registry
        self.issues: List[SyncIssue] = []
    
    def check(self) -> List[SyncIssue]:
        """Perform sync check."""
        self._find_unregistered_agents()
        self._find_broken_references()
        self._find_duplicate_names()
        
        return self.issues
    
    def _find_unregistered_agents(self):
        """Find agents that aren't in the registry."""
        for agent_key, agent in self.agents.items():
            # Skip abstract agents (they're not meant to be instantiated directly)
            if agent.is_abstract:
                continue
            
            # Check if this agent is registered (by class name or full path)
            is_registered = (
                agent.name in self.registry or
                agent_key.split('.')[-1] in self.registry or
                any(agent.name in ref for ref in [e.agent_class_ref for e in self.registry.values()])
            )
            
            if not is_registered:
                severity = 'WARNING'
                
                # Higher severity if it has a run method (concrete, usable agent)
                if agent.has_run_method:
                    severity = 'CRITICAL'
                
                suggestion = (
                    f"Add '{agent.name}' to agent registry in one of: "
                    f"{', '.join(set(e.file_path for e in self.registry.values()))}"
                )
                
                self.issues.append(SyncIssue(
                    issue_type='UNREGISTERED_AGENT',
                    severity=severity,
                    agent_name=agent.name,
                    description=f"Agent '{agent.name}' ({agent_key}) is defined but not in registry",
                    location=f"{agent.file_path}:{agent.line_number}",
                    suggestion=suggestion
                ))
    
    def _find_broken_references(self):
        """Find registry entries that don't point to valid agents."""
        for reg_name, entry in self.registry.items():
            ref = entry.agent_class_ref
            
            # Check if this reference points to a real agent
            is_valid = (
                ref in self.agents or
                any(ref in key or ref == ag.name for key, ag in self.agents.items()) or
                ref == "?"  # Unknown refs get a pass
            )
            
            if not is_valid and ref != "?":
                self.issues.append(SyncIssue(
                    issue_type='BROKEN_REGISTRY_REF',
                    severity='WARNING',
                    agent_name=reg_name,
                    description=f"Registry entry '{reg_name}' references '{ref}' which doesn't match any Agent class",
                    location=entry.file_path,
                    registry_location=f"{entry.file_path}:{entry.line_number}",
                    suggestion=f"Update reference to point to valid Agent class or remove stale entry"
                ))
    
    def _find_duplicate_names(self):
        """Find potential naming conflicts."""
        name_counts = defaultdict(list)
        
        for agent_key, agent in self.agents.items():
            name_counts[agent.name].append(agent_key)
        
        for name, keys in name_counts.items():
            if len(keys) > 1:
                locations = [f"{self.agents[k].file_path}:{self.agents[k].line_number}" for k in keys]
                
                self.issues.append(SyncIssue(
                    issue_type='DUPLICATE_NAME',
                    severity='INFO',
                    agent_name=name,
                    description=f"Multiple Agent classes named '{name}' found",
                    location=', '.join(locations),
                    suggestion="Consider renaming to avoid confusion"
                ))


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, issues: List[SyncIssue], agents: Dict[str, AgentDefinition],
                 registry: Dict[str, RegistryEntry]):
        self.issues = sorted(issues, key=lambda x: (
            {'CRITICAL': 0, 'WARNING': 1, 'INFO': 2}.get(x.severity, 3),
            x.issue_type
        ))
        self.agents = agents
        self.registry = registry
        
        # Summary stats
        critical = sum(1 for i in issues if i.severity == 'CRITICAL')
        warnings = sum(1 for i in issues if i.severity == 'WARNING')
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI AGENT CAPABILITY REGISTRY SYNC CHECKER")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Agent Definitions Found:     {len(self.agents)}")
        lines.append(f"  Registry Entries Found:      {len(self.registry)}")
        lines.append(f"  Sync Issues:                {len(self.issues)}")
        lines.append(f"    Critical:                  {critical}")
        lines.append(f"    Warnings:                  {warnings}")
        lines.append("")
        
        # Issues by type
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.issue_type].append(issue)
        
        # Unregistered Agents
        if 'UNREGISTERED_AGENT' in by_type:
            unregistered = by_type['UNREGISTERED_AGENT']
            lines.append("\n🔴 UNREGISTERED AGENTS (Defined but Not in Registry)")
            lines.append("=" * 40)
            
            for i, issue in enumerate(unregistered, 1):
                lines.append(f"\n  {i}. [{issue.severity}] {issue.agent_name}")
                lines.append(f"     Location: {issue.location}")
                lines.append(f"     {issue.description}")
                lines.append(f"     💡 {issue.suggestion}")
        
        # Broken References
        if 'BROKEN_REGISTRY_REF' in by_type:
            broken = by_type['BROKEN_REGISTRY_REF']
            lines.append(f"\n\n⚠️ BROKEN REGISTRY REFERENCES: {len(broken)}")
            lines.append("-" * 40)
            
            for issue in broken:
                lines.append(f"  • '{issue.agent_name}' → {issue.description}")
                lines.append(f"    at {issue.location}")
        
        # Duplicate Names
        if 'DUPLICATE_NAME' in by_type:
            dupes = by_type['DUPLICATE_NAME']
            lines.append(f"\n\nℹ️ DUPLICATE NAMES: {len(dupes)}")
            lines.append("-" * 40)
            
            for issue in dupes:
                lines.append(f"  • {issue.agent_name}: {issue.description}")
        
        # All discovered agents (for reference)
        lines.append("\n\n📋 ALL DISCOVERED AGENTS")
        lines.append("-" * 40)
        
        concrete_agents = [a for a in self.agents.values() if not a.is_abstract]
        abstract_agents = [a for a in self.agents.values() if a.is_abstract]
        
        lines.append(f"\n  Concrete Agents ({len(concrete_agents)}):")
        for agent in sorted(concrete_agents, key=lambda a: a.name):
            reg_status = "✓" if agent.name in self.registry else "✗"
            lines.append(f"    [{reg_status}] {agent.name} ({agent.module})")
        
        if abstract_agents:
            lines.append(f"\n  Abstract/Base Agents ({len(abstract_agents)}):")
            for agent in sorted(abstract_agents, key=lambda a: a.name):
                lines.append(f"    [A] {agent.name} ({agent.module})")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Immediate Actions:
1. Register all CRITICAL unregistered agents
2. Fix or remove broken registry references
3. Resolve duplicate naming conflicts

Prevention:
1. Add this script to CI pipeline
2. Create convention: new Agent must be registered immediately
3. Consider using decorators (@register_agent) for auto-registration
4. Document agent creation workflow

Registry Best Practices:
- Keep registry in single source of truth
- Include metadata with each entry (description, capabilities, version)
- Validate registry on startup
- Support dynamic registration for plugins
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total_agents": len(self.agents),
                "registered_agents": len(self.registry),
                "sync_issues": len(self.issues),
                "critical_issues": sum(1 for i in self.issues if i.severity == 'CRITICAL'),
                "warning_issues": sum(1 for i in self.issues if i.severity == 'WARNING'),
            },
            "agents": [{
                "name": a.name,
                "module": a.module,
                "file": a.file_path,
                "is_abstract": a.is_abstract,
                "is_registered": a.name in self.registry,
                "capabilities": a.capabilities
            } for a in self.agents.values()],
            "issues": [asdict(i) for i in self.issues],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Agent Capability Registry Sync Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory (default: ../backend)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit with error code if critical issues found')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print(f"🤖 SupremeAI Agent Capability Registry Sync Checker")
    print(f"   Backend: {backend_dir}")
    print()
    
    # Scan for agents
    agent_scanner = AgentScanner(backend_dir)
    agents = agent_scanner.scan()
    
    # Scan for registry
    reg_scanner = RegistryScanner(backend_dir)
    registry = reg_scanner.scan()
    
    # Check sync
    checker = SyncChecker(agents, registry)
    issues = checker.check()
    
    # Generate report
    generator = ReportGenerator(issues, agents, registry)
    
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
    critical_count = sum(1 for i in issues if i.severity == 'CRITICAL')
    if args.fail_on_critical and critical_count > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
