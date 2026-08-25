#!/usr/bin/env python3
"""
Dead Code Verified Finder for SupremeAI
=========================================
Uses strict import-graph traversal to find truly dead modules and code.
Unlike loose grep-based tools, this analyzes actual import dependencies.

Detects:
- Modules that are never imported by any other module
- Functions/classes that are defined but never called/used
- Unused exports from modules
- Orphaned files not part of any import chain

Usage:
    python dead_code_verified_finder.py [--backend-dir ../backend] [--output-format text|json]
    
Self-healing principles:
- AST-based analysis (not regex)
- Follows actual import chains
- Distinguishes between dead code and entry points
"""

import ast
import os
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
class ModuleInfo:
    """Information about a Python module."""
    name: str
    file_path: str
    is_package_init: bool = False
    is_entry_point: bool = False  # Has __main__ or is run directly
    imports_from: Set[str] = field(default_factory=set)  # Who imports this module
    imports_to: Set[str] = field(default_factory=set)  # What this module imports
    exports: List[str] = field(default_factory=list)  # Public names (no _ prefix)
    all_defined_names: Set[str] = field(default_factory=set)  # All definitions
    used_names: Set[str] = field(default_factory=set)  # Names used internally


@dataclass
class DeadCodeFinding:
    """A finding about potentially dead code."""
    finding_type: str  # 'dead_module', 'unused_export', 'orphan_file', 'unused_function', 'unused_class'
    name: str
    file_path: str
    line_number: int = 0
    confidence: float = 0.0  # How sure we are it's truly dead
    reason: str = ""
    suggestion: str = ""
    imported_by: List[str] = field(default_factory=list)


class ImportGraphBuilder:
    """Builds a complete import graph using AST."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.modules: Dict[str, ModuleInfo] = {}
        
    def build(self) -> Dict[str, ModuleInfo]:
        """Build complete import graph."""
        py_files = self._find_python_files()
        
        for py_file in py_files:
            module_name = self._file_to_module(py_file)
            self._analyze_module(py_file, module_name)
        
        # Resolve internal imports (within project)
        self._resolve_internal_imports()
        
        logger.info(f"Built import graph with {len(self.modules)} modules")
        return self.modules
    
    def _find_python_files(self) -> List[Path]:
        """Find all Python files in project."""
        skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'dist', 
                    'build', '.tox', 'node_modules', '__pycache__'}
        
        py_files = []
        for py_file in self.project_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            
            # Skip migration files (they're special)
            if 'migrations' in str(py_file):
                continue
                
            py_files.append(py_file)
        
        return py_files
    
    def _file_to_module(self, file_path: Path) -> str:
        """Convert file path to module name."""
        rel = file_path.relative_to(self.project_dir.parent)
        parts = list(rel.parts)
        
        # Remove .py extension
        if parts[-1].endswith('.py'):
            parts[-1] = parts[-1][:-3]
        
        # Handle __init__.py
        if parts[-1] == '__init__':
            parts.pop()
        
        return '.'.join(parts)
    
    def _analyze_module(self, file_path: Path, module_name: str):
        """Analyze a single module's imports and definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            return
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        is_init = file_path.name == '__init__.py'
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        
        module_info = ModuleInfo(
            name=module_name,
            file_path=rel_path,
            is_package_init=is_init,
            is_entry_point=self._is_entry_point(tree),
            exports=[],
            all_defined_names=set(),
            used_names=set()
        )
        
        # Analyze imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_info.imports_to.add(alias.name)
                    
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    level = node.level or 0
                    if level > 0:
                        # Relative import - resolve later
                        module_info.imports_to.add(f"{'.' * level}{node.module}")
                    else:
                        module_info.imports_to.add(node.module)
            
            # Track definitions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module_info.all_defined_names.add(node.name)
                if not node.name.startswith('_'):
                    module_info.exports.append(node.name)
                    
            elif isinstance(node, ast.ClassDef):
                module_info.all_defined_names.add(node.name)
                if not node.name.startswith('_'):
                    module_info.exports.append(node.name)
            
            # Track assignments (module-level variables)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_info.all_defined_names.add(target.id)
                        if not target.id.startswith('_'):
                            module_info.exports.append(target.id)
            
            # Track usage of names
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    module_info.used_names.add(node.id)
        
        self.modules[module_name] = module_info
    
    def _is_entry_point(self, tree: ast.AST) -> bool:
        """Check if module is an entry point (has __main__ guard)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check for if __name__ == "__main__"
                test = node.test
                if isinstance(test, ast.Compare):
                    left = test.left
                    if isinstance(left, ast.Name) and left.id == '__name__':
                        return True
        return False
    
    def _resolve_internal_imports(self):
        """Resolve which imports are internal to this project."""
        # Build set of known module prefixes
        known_modules = set(self.modules.keys())
        
        for module_name, info in self.modules.items():
            resolved_imports = set()
            
            for imp in info.imports_to:
                # Check if this import is within our project
                is_internal = False
                
                # Direct match
                if imp in known_modules:
                    is_internal = True
                else:
                    # Prefix match (importing submodule)
                    for known in known_modules:
                        if imp.startswith(known + '.') or known.startswith(imp + '.'):
                            is_internal = True
                            break
                
                if is_internal:
                    resolved_imports.add(imp)
                    
                    # Record that target is imported by this module
                    # Find best matching target module
                    target_module = self._best_match(imp, known_modules)
                    if target_module and target_module in self.modules:
                        self.modules[target_module].imports_from.add(module_name)
            
            info.imports_to = resolved_imports
    
    def _best_match(self, import_name: str, known_modules: Set[str]) -> Optional[str]:
        """Find best matching module for an import."""
        if import_name in known_modules:
            return import_name
        
        # Try adding/removing parts
        base = import_name.rstrip('.')
        while '.' in base:
            if base in known_modules:
                return base
            base = base.rsplit('.', 1)[0]
        
        return None


class DeadCodeAnalyzer:
    """Analyzes import graph to find dead code."""
    
    # Common entry points that shouldn't be flagged
    ENTRY_POINT_PATTERNS = {
        '__main__', 'main.py', 'app.py', 'server.py',
        'manage.py', 'cli.py', 'run.py', 'start.py'
    }
    
    # Common test patterns
    TEST_PATTERNS = {'test_', '_test.', 'tests/', 'conftest.py'}
    
    def __init__(self, modules: Dict[str, ModuleInfo]):
        self.modules = modules
        self.findings: List[DeadCodeFinding] = []
    
    def analyze(self) -> List[DeadCodeFinding]:
        """Perform dead code analysis."""
        self._find_dead_modules()
        self._find_unused_exports()
        self._find_orphan_files()
        
        return self.findings
    
    def _is_test_module(self, module_name: str, file_path: str) -> bool:
        """Check if this is a test module."""
        for pattern in self.TEST_PATTERNS:
            if pattern in module_name.lower() or pattern in file_path.lower():
                return True
        return False
    
    def _is_likely_entry_point(self, module: ModuleInfo) -> bool:
        """Check if module might be an entry point."""
        if module.is_entry_point:
            return True
        
        for pattern in self.ENTRY_POINT_PATTERNS:
            if pattern in module.file_path or pattern in module.name:
                return True
        
        # Entry points often have minimal imports but many definitions
        if len(module.imports_to) <= 3 and len(module.exports) >= 5:
            return True
        
        return False
    
    def _find_dead_modules(self):
        """Find modules that are never imported by any other module."""
        for module_name, module in self.modules.items():
            # Skip tests
            if self._is_test_module(module_name, module.file_path):
                continue
            
            # Skip entry points
            if self._is_likely_entry_point(module):
                continue
            
            # Skip package init files (they define the package)
            if module.is_package_init:
                continue
            
            # If nobody imports this module, it might be dead
            if not module.imports_from:
                confidence = 0.9
                
                # Reduce confidence if it looks like it could be run standalone
                if module.is_entry_point:
                    confidence = 0.4
                elif 'main' in module.name.lower() or 'run' in module.name.lower():
                    confidence = 0.5
                
                # Increase confidence if it has no imports either (truly isolated)
                if not module.imports_to:
                    confidence = min(confidence + 0.05, 1.0)
                
                self.findings.append(DeadCodeFinding(
                    finding_type='dead_module',
                    name=module_name,
                    file_path=module.file_path,
                    confidence=confidence,
                    reason="Module is not imported by any other module",
                    suggestion="Remove if unused, or add to documentation as entry point"
                ))
    
    def _find_unused_exports(self):
        """Find exported functions/classes that are never used externally."""
        for module_name, module in self.modules.items():
            # Skip tests
            if self._is_test_module(module_name, module.file_path):
                continue
            
            # For each export, check if it's likely used
            for export_name in module.exports:
                # Skip common dunder methods and special names
                if export_name.startswith('__') and export_name.endswith('__'):
                    continue
                
                # Skip very common names that might be used dynamically
                if export_name in ('logger', 'log', 'config', 'settings', 'app', 
                                  'router', 'db', 'Base', 'Model'):
                    continue
                
                # Check if used internally
                if export_name in module.used_names:
                    continue  # Used within the module itself
                
                # This is a heuristic - we can't know for sure without runtime analysis
                # But high confidence cases include:
                # - Single-function modules where function isn't called
                confidence = 0.6  # Medium confidence by default
                
                # Higher confidence if module only defines this one thing
                if len(module.exports) == 1:
                    confidence = 0.75
                
                # Lower confidence for common patterns
                if export_name.startswith(('get_', 'set_', 'handle_', 'process_')):
                    confidence -= 0.1
                
                if confidence >= 0.6:  # Only report medium+ confidence
                    self.findings.append(DeadCodeFinding(
                        finding_type='unused_export',
                        name=export_name,
                        file_path=module.file_path,
                        confidence=confidence,
                        reason=f"Export '{export_name}' is not used within its own module",
                        suggestion=f"Verify if '{export_name}' is used via dynamic import or external reference"
                    ))
    
    def _find_orphan_files(self):
        """Find Python files that appear completely orphaned."""
        # Find files that exist on disk but weren't part of our analysis
        analyzed_files = {m.file_path for m in self.modules.values()}
        
        # This would require re-scanning; for now just flag modules with no connections
        isolated_modules = [
            m for m in self.modules.values() 
            if not m.imports_from and not m.imports_to
        ]
        
        for module in isolated_modules:
            if self._is_test_module(module.name, module.file_path):
                continue
            
            self.findings.append(DeadCodeFinding(
                finding_type='orphan_file',
                name=module.name,
                file_path=module.file_path,
                confidence=0.85,
                reason="File has no import connections at all",
                suggestion="Consider removing or documenting purpose"
            ))


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, findings: List[DeadCodeFinding], modules: Dict[str, ModuleInfo]):
        self.findings = sorted(findings, key=lambda x: (-x.confidence, x.file_path, x.name))
        self.modules = modules
        
        # Summary stats
        self.dead_modules = sum(1 for f in findings if f.finding_type == 'dead_module')
        self.unused_exports = sum(1 for f in findings if f.finding_type == 'unused_export')
        self.orphan_files = sum(1 for f in findings if f.finding_type == 'orphan_file')
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI DEAD CODE VERIFIED FINDER REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Modules Analyzed:           {len(self.modules)}")
        lines.append(f"  Total Findings:             {len(self.findings)}")
        lines.append(f"    - Dead Modules:           {self.dead_modules}")
        lines.append(f"    - Unused Exports:         {self.unused_exports}")
        lines.append(f"    - Orphan Files:           {self.orphan_files}")
        lines.append("")
        
        # Group by type
        by_type = defaultdict(list)
        for finding in self.findings:
            by_type[finding.finding_type].append(finding)
        
        # Dead Modules
        if 'dead_module' in by_type:
            lines.append("\n🔴 DEAD MODULES (Never Imported)")
            lines.append("-" * 40)
            for i, finding in enumerate(by_type['dead_module'][:30], 1):
                conf_icon = "✓" if finding.confidence >= 0.8 else "?"
                lines.append(f"\n  {i}. [{conf_icon} {finding.confidence:.0%}] {finding.name}")
                lines.append(f"     File: {finding.file_path}")
                lines.append(f"     Why: {finding.reason}")
                lines.append(f"     💡 {finding.suggestion}")
            
            if len(by_type['dead_module']) > 30:
                lines.append(f"\n  ... and {len(by_type['dead_module']) - 30} more")
        
        # Unused Exports
        if 'unused_export' in by_type:
            lines.append("\n\n⚠️ POTENTIALLY UNUSED EXPORTS")
            lines.append("-" * 40)
            lines.append("  (These may be used via dynamic imports or external references)")
            
            for i, finding in enumerate(by_type['unused_export'][:20], 1):
                lines.append(f"\n  {i}. [{finding.confidence:.0%}] {finding.name} in {finding.file_path}")
                lines.append(f"     💡 {finding.suggestion}")
            
            if len(by_type['unused_export']) > 20:
                lines.append(f"\n  ... and {len(by_type['unused_export']) - 20} more")
        
        # Orphan Files
        if 'orphan_file' in by_type:
            lines.append("\n\n📄 ORPHAN FILES (No Import Connections)")
            lines.append("-" * 40)
            for finding in by_type['orphan_file']:
                lines.append(f"  • {finding.file_path} ({finding.name})")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Before Deleting Any Code:
1. Search for string references (some imports may be dynamic)
2. Check if it's registered somewhere (plugins, entry points)
3. Look for test files that import it
4. Verify it's not documented as public API

Safe Removal Process:
1. Comment out or move to 'attic/' directory
2. Run full test suite
3. Wait one sprint cycle
4. If no complaints, delete permanently

Prevention:
- Add this script to CI to catch new dead code early
- Review new module additions in code review
- Use architecture docs to track intended module usage
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "modules_analyzed": len(self.modules),
                "total_findings": len(self.findings),
                "dead_modules": self.dead_modules,
                "unused_exports": self.unused_exports,
                "orphan_files": self.orphan_files,
            },
            "findings": [asdict(f) for f in self.findings],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Dead Code Finder - Uses strict import graph analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory (default: ../backend)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                       help='Minimum confidence threshold (default: 0.5)')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print(f"🗑️ SupremeAI Dead Code Verified Finder")
    print(f"   Backend: {backend_dir}")
    print()
    
    # Build import graph
    builder = ImportGraphBuilder(backend_dir)
    modules = builder.build()
    
    # Analyze for dead code
    analyzer = DeadCodeAnalyzer(modules)
    findings = analyzer.analyze()
    
    # Filter by confidence
    filtered = [f for f in findings if f.confidence >= args.min_confidence]
    
    # Generate report
    generator = ReportGenerator(filtered, modules)
    
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
    
    return 0


if __name__ == '__main__':
    main()
