#!/usr/bin/env python3
"""
Circular Import Mapper for SupremeAI
======================================
Builds a complete import graph across the backend codebase and
detects circular dependency chains that can cause silent slowdowns,
import errors, or crashes in monorepo-scale projects.

Features:
- AST-based import extraction (not regex)
- Visualizes dependency chains
- Detects direct and indirect circular imports
- Identifies high-risk modules (heavily imported, many dependencies)

Usage:
    python circular_import_mapper.py [--backend-dir ../backend] [--output-format text|dot|json]
    
Self-healing principles:
- Fully dynamic - no hardcoded module lists
- Auto-discovers all Python modules
- CI-friendly with exit codes
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
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImportType(Enum):
    STANDARD = "standard"
    FROM_IMPORT = "from_import"
    RELATIVE = "relative"
    DYNAMIC = "dynamic"  # __import__, importlib


@dataclass
class ImportEdge:
    """Represents an import relationship between two modules."""
    source_module: str  # The module doing the importing
    target_module: str  # The module being imported
    import_type: ImportType
    names: List[str] = field(default_factory=list)  # What's being imported (functions, classes, etc.)
    line_number: int = 0
    is_lazy: bool = False  # Lazy/import-inside-function detection


@dataclass
class ModuleNode:
    """Represents a Python module in the import graph."""
    name: str
    file_path: str
    is_package: bool = False
    is_init: bool = False
    imports_out: List[ImportEdge] = field(default_factory=list)  # This module imports these
    imports_in: List[ImportEdge] = field(default_factory=list)  # These modules import this
    line_count: int = 0
    complexity_score: float = 0.0  # Based on import count and connections


@dataclass
class CircularChain:
    """Represents a detected circular import chain."""
    chain: List[str]  # Module names in cycle order
    cycle_length: int
    severity: str  # CRITICAL, WARNING, INFO
    edges: List[ImportEdge] = field(default_factory=list)
    impact_description: str = ""
    suggestion: str = ""


@dataclass
class RiskModule:
    """A module identified as high-risk based on import patterns."""
    module_name: str
    risk_type: str  # "hub", "heavy", "deeply_nested", "coupled"
    score: float
    description: str
    metrics: Dict[str, Any] = field(default_factory=dict)


class ASTImportExtractor:
    """Extracts import information using AST analysis."""
    
    def __init__(self):
        self.edges: List[ImportEdge] = []
        self.modules: Dict[str, ModuleNode] = {}
    
    def extract_from_directory(self, directory: Path, base_package: str = "") -> Tuple[List[ImportEdge], Dict[str, ModuleNode]]:
        """Extract all imports from a directory of Python files."""
        py_files = list(directory.rglob("*.py"))
        
        skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'dist', 
                    'build', '.tox', 'migrations', 'tests'}
        
        for py_file in py_files:
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            
            rel_path = py_file.relative_to(directory.parent)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
            
            if base_package:
                module_name = f"{base_package}.{module_name}" if module_name != base_package else base_package
            
            self._process_file(py_file, module_name)
        
        # Build reverse references (imports_in)
        for edge in self.edges:
            if edge.target_module in self.modules:
                self.modules[edge.target_module].imports_in.append(edge)
        
        return self.edges, self.modules
    
    def _process_file(self, file_path: Path, module_name: str):
        """Process a single Python file for imports."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            return
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        # Create module node
        is_init = file_path.name == '__init__.py'
        is_package = is_init or any((file_path.parent / i).exists() for i in ['__init__.py'])
        
        node = ModuleNode(
            name=module_name,
            file_path=str(file_path),
            is_package=is_package,
            is_init=is_init,
            line_count=len(lines)
        )
        self.modules[module_name] = node
        
        # Extract imports
        for item in ast.iter_child_nodes(tree):
            if isinstance(item, ast.Import):
                self._handle_import(item, module_name, lines)
            elif isinstance(item, ast.ImportFrom):
                self._handle_import_from(item, module_name, lines)
    
    def _handle_import(self, node: ast.Import, source_module: str, lines: List[str]):
        """Handle: import X, import X as Y, import X.Y.Z"""
        for alias in node.names:
            target_module = alias.name
            
            edge = ImportEdge(
                source_module=source_module,
                target_module=target_module,
                import_type=ImportType.STANDARD,
                names=[alias.asname or alias.name],
                line_number=node.lineno
            )
            
            self.edges.append(edge)
            self.modules[source_module].imports_out.append(edge)
    
    def _handle_import_from(self, node: ast.ImportFrom, source_module: str, lines: List[str]):
        """Handle: from X import Y, from .X import Y, from ..X import Y"""
        # Determine the actual module being imported from
        if node.module:
            # Handle relative imports
            level = node.level or 0
            if level > 0:
                # Relative import: calculate base from source_module
                parts = source_module.split('.')
                
                # Go up 'level' directories from current package
                if level <= len(parts):
                    base_parts = parts[:-level] if level < len(parts) else []
                    target_base = '.'.join(base_parts)
                    target_module = f"{target_base}.{node.module}" if target_base else node.module
                else:
                    target_module = node.module
                
                import_type = ImportType.RELATIVE
            else:
                target_module = node.module
                import_type = ImportType.FROM_IMPORT
        else:
            # from . import X (rare)
            target_module = source_module.rsplit('.', 1)[0] if '.' in source_module else ''
            import_type = ImportType.RELATIVE
        
        if not target_module:
            return
        
        # Get imported names
        names = [a.asname or a.name for a in node.names]
        
        # Check if inside function (lazy import)
        is_lazy = self._is_inside_function(node.lineno, lines)
        
        edge = ImportEdge(
            source_module=source_module,
            target_module=target_module,
            import_type=import_type,
            names=names,
            line_number=node.lineno,
            is_lazy=is_lazy
        )
        
        self.edges.append(edge)
        self.modules[source_module].imports_out.append(edge)
    
    def _is_inside_function(self, line_num: int, lines: List[str]) -> bool:
        """Check if an import at line_num is inside a function (lazy import)."""
        # Simple heuristic: check indentation depth before this line
        indent_stack = []
        
        for i in range(min(line_num - 1, len(lines))):
            line = lines[i]
            stripped = line.strip()
            
            # Skip comments and empty lines
            if not stripped or stripped.startswith('#'):
                continue
            
            # Count indentation
            indent = len(line) - len(line.lstrip())
            
            # Check for function/class definitions
            if re.match(r'(def|class)\s+\w+', stripped):
                indent_stack.append(indent)
            elif indent_stack and indent < indent_stack[-1]:
                indent_stack.pop()
        
        return len(indent_stack) > 0


class CircularDependencyDetector:
    """Detects circular dependencies in the import graph."""
    
    def __init__(self, edges: List[ImportEdge], modules: Dict[str, ModuleNode]):
        self.edges = edges
        self.modules = modules
        self.chains: List[CircularChain] = []
        
        # Build adjacency list for faster traversal
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
        self.edge_map: Dict[Tuple[str, str], ImportEdge] = {}
        
        for edge in edges:
            self.adjacency[edge.source_module].add(edge.target_module)
            self.edge_map[(edge.source_module, edge.target_module)] = edge
    
    def detect_cycles(self) -> List[CircularChain]:
        """Detect all circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        path = []
        
        # Start DFS from each module
        for module_name in self.modules:
            if module_name not in visited:
                self._dfs(module_name, visited, rec_stack, path)
        
        # Deduplicate cycles (same cycle can be found starting from different points)
        unique_chains = []
        seen_chain_sets = set()
        
        for chain in self.chains:
            # Normalize: rotate to start with smallest element (lexicographically)
            normalized = self._normalize_cycle(chain.chain)
            chain_key = tuple(normalized)
            
            if chain_key not in seen_chain_sets:
                seen_chain_sets.add(chain_key)
                unique_chains.append(chain)
        
        self.chains = unique_chains
        logger.info(f"Found {len(unique_chains)} unique circular dependency chains")
        
        return self.chains
    
    def _dfs(self, module: str, visited: Set[str], rec_stack: Set[str], path: List[str]):
        """DFS to find cycles."""
        visited.add(module)
        rec_stack.add(module)
        path.append(module)
        
        for neighbor in self.adjacency.get(module, set()):
            if neighbor not in visited:
                self._dfs(neighbor, visited, rec_stack, path)
            elif neighbor in rec_stack:
                # Found a cycle!
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                
                # Get edges involved
                edges_in_cycle = []
                for i in range(len(cycle) - 1):
                    edge = self.edge_map.get((cycle[i], cycle[i+1]))
                    if edge:
                        edges_in_cycle.append(edge)
                
                # Determine severity
                severity = self._assess_severity(cycle, edges_in_cycle)
                
                chain = CircularChain(
                    chain=cycle,
                    cycle_length=len(cycle) - 1,
                    severity=severity,
                    edges=edges_in_cycle,
                    impact_description=self._describe_impact(cycle),
                    suggestion=self._suggest_fix(cycle, edges_in_cycle)
                )
                
                self.chains.append(chain)
        
        path.pop()
        rec_stack.remove(module)
    
    def _normalize_cycle(self, cycle: List[str]) -> List[str]:
        """Normalize cycle representation for deduplication."""
        if len(cycle) <= 1:
            return cycle
        
        # Remove duplicate last element (cycle closure)
        items = cycle[:-1] if cycle[0] == cycle[-1] else cycle[:]
        
        # Find minimum rotation
        min_idx = 0
        for i in range(1, len(items)):
            if items[i] < items[min_idx]:
                min_idx = i
        
        rotated = items[min_idx:] + items[:min_idx]
        return rotated
    
    def _assess_severity(self, cycle: List[str], edges: List[ImportEdge]) -> str:
        """Assess severity of a circular dependency."""
        # All non-lazy imports = CRITICAL
        if all(not e.is_lazy for e in edges):
            return 'CRITICAL'
        
        # Involves __init__.py files = often problematic
        if any('__init__' in m for m in cycle):
            return 'WARNING'
        
        # Long chains are worse
        if len(cycle) > 4:
            return 'WARNING'
        
        return 'INFO'
    
    def _describe_impact(self, cycle: List[str]) -> str:
        """Describe the potential impact of this circular dependency."""
        modules_str = ' → '.join(cycle[:-1])
        
        impacts = [
            f"Creates circular dependency: {modules_str} → {cycle[-1]}",
            "May cause ImportError at runtime",
            "Can lead to incomplete initialization of module-level objects"
        ]
        
        # Check for specific patterns
        init_modules = [m for m in cycle if '__init__' in m]
        if init_modules:
            impacts.append(f"Involves package __init__ files: {[Path(m).name for m in init_modules]}")
        
        lazy_edges = [e for e in self.edges if e.is_lazy and e.source_module in cycle and e.target_module in cycle]
        if lazy_edges:
            impacts.append(f"Some imports may be lazy (inside functions): {len(lazy_edges)}")
        
        return '. '.join(impacts)
    
    def _suggest_fix(self, cycle: List[str], edges: List[ImportEdge]) -> str:
        """Suggest fixes for the circular dependency."""
        suggestions = [
            "Consider refactoring shared code into a separate utility module",
            "Use lazy imports (import inside functions) where possible",
            "Move shared dependencies to a lower-level module"
        ]
        
        # Check for specific patterns
        type_hints = [e for e in edges if any(n.startswith('TYPE_CHECKING') or n == 'Optional' 
                                                  for n in e.names)]
        if type_hints:
            suggestions.insert(0, "Wrap type hint imports in `if TYPE_CHECKING:` blocks")
        
        init_involved = any('__init__' in m for m in cycle)
        if init_involved:
            suggestions.insert(0, "Move imports out of __init__.py files into submodule level")
        
        return suggestions[0]


class RiskAnalyzer:
    """Analyzes modules for risky import patterns."""
    
    def __init__(self, modules: Dict[str, ModuleNode], edges: List[ImportEdge]):
        self.modules = modules
        self.edges = edges
        self.risk_modules: List[RiskModule] = []
        
        # Build statistics
        self.in_degree: Dict[str, int] = defaultdict(int)  # How many import this
        self.out_degree: Dict[str, int] = defaultdict(int)  # How many this imports
        
        for edge in edges:
            self.in_degree[edge.target_module] += 1
            self.out_degree[edge.source_module] += 1
    
    def analyze(self) -> List[RiskModule]:
        """Identify high-risk modules."""
        self._find_hub_modules()
        self._find_heavy_modules()
        self._find_coupled_modules()
        self._calculate_complexity_scores()
        
        # Sort by score descending
        self.risk_modules.sort(key=lambda x: x.score, reverse=True)
        
        return self.risk_modules
    
    def _find_hub_modules(self):
        """Find modules that are imported by many others (hub pattern)."""
        avg_in = sum(self.in_degree.values()) / max(len(self.in_degree), 1)
        threshold = avg_in * 2  # More than 2x average
        
        for module_name, degree in self.in_degree.items():
            if degree >= threshold and degree >= 5:  # At least 5 importers
                self.risk_modules.append(RiskModule(
                    module_name=module_name,
                    risk_type="hub",
                    score=min(degree / 10, 10.0),  # Normalize to ~0-10
                    description=f"Hub module imported by {degree} other modules",
                    metrics={"in_degree": degree, "threshold": threshold}
                ))
    
    def _find_heavy_modules(self):
        """Find modules with too many outgoing imports."""
        avg_out = sum(self.out_degree.values()) / max(len(self.out_degree), 1)
        threshold = avg_out * 3  # More than 3x average
        
        for module_name, degree in self.out_degree.items():
            if degree >= threshold and degree >= 10:  # At least 10 imports
                self.risk_modules.append(RiskModule(
                    module_name=module_name,
                    risk_type="heavy",
                    score=min(degree / 20, 10.0),
                    description=f"Heavy module with {degree} imports (avg: {avg_out:.1f})",
                    metrics={"out_degree": degree, "average": avg_out}
                ))
    
    def _find_coupled_modules(self):
        """Find pairs of modules that import each other (bidirectional coupling)."""
        coupled_pairs = set()
        
        for edge in self.edges:
            reverse_exists = any(
                e.target_module == edge.source_module and e.source_module == edge.target_module
                for e in self.edges
            )
            if reverse_exists:
                pair = tuple(sorted([edge.source_module, edge.target_module]))
                coupled_pairs.add(pair)
        
        for mod_a, mod_b in coupled_pairs:
            self.risk_modules.append(RiskModule(
                module_name=f"{mod_a} ↔ {mod_b}",
                risk_type="coupled",
                score=7.0,
                description=f"Bidirectional coupling detected",
                metrics={"module_a": mod_a, "module_b": mod_b}
            ))
    
    def _calculate_complexity_scores(self):
        """Calculate overall complexity scores for all modules."""
        for module_name, node in self.modules.items():
            # Combine factors
            in_d = self.in_degree.get(module_name, 0)
            out_d = self.out_degree.get(module_name, 0)
            
            # Complexity = weighted combination
            complexity = (
                in_d * 0.3 +  # Being imported by many = responsibility
                out_d * 0.2 +  # Importing many = coupling
                min(node.line_count / 100, 5) * 0.3 +  # Large files
                (1 if node.is_init else 0) * 1  # __init__ files add complexity
            )
            
            node.complexity_score = complexity


class ReportGenerator:
    """Generates reports in various formats."""
    
    def __init__(self, chains: List[CircularChain], risk_modules: List[RiskModule],
                 modules: Dict[str, ModuleNode], edges: List[ImportEdge]):
        self.chains = chains
        self.risk_modules = risk_modules
        self.modules = modules
        self.edges = edges
    
    def generate_text_report(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI CIRCULAR IMPORT MAPPER REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary stats
        critical_chains = [c for c in self.chains if c.severity == 'CRITICAL']
        warning_chains = [c for c in self.chains if c.severity == 'WARNING']
        
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Modules Analyzed:           {len(self.modules)}")
        lines.append(f"  Import Relationships:       {len(self.edges)}")
        lines.append(f"  Circular Dependencies:      {len(self.chains)}")
        lines.append(f"    - Critical:               {len(critical_chains)}")
        lines.append(f"    - Warning:                {len(warning_chains)}")
        lines.append(f"  High-Risk Modules:          {len(self.risk_modules)}")
        lines.append("")
        
        # Circular Dependencies Section
        if self.chains:
            lines.append("\n🔄 CIRCULAR DEPENDENCIES DETECTED")
            lines.append("=" * 40)
            
            for i, chain in enumerate(self.chains[:20], 1):  # Limit output
                severity_icon = {'CRITICAL': '🔴', 'WARNING': '⚠️', 'INFO': 'ℹ️'}.get(chain.severity, '')
                lines.append(f"\n  {i}. {severity_icon} [{chain.severity}] Cycle length: {chain.cycle_length}")
                lines.append(f"     Chain: {' → '.join(chain.chain)}")
                lines.append(f"     Impact: {chain.impact_description}")
                lines.append(f"     💡 Fix: {chain.suggestion}")
            
            if len(self.chains) > 20:
                lines.append(f"\n  ... and {len(self.chains) - 20} more circular dependencies")
        
        # High-Risk Modules Section
        if self.risk_modules:
            lines.append("\n\n⚠️ HIGH-RISK MODULES")
            lines.append("=" * 40)
            
            risk_types = {
                'hub': '🎯 Hub (too central)',
                'heavy': '📦 Heavy (too many imports)',
                'coupled': '🔗 Coupled (bidirectional)'
            }
            
            for i, risk in enumerate(self.risk_modules[:15], 1):
                type_label = risk_types.get(risk.risk_type, risk.risk_type)
                lines.append(f"\n  {i}. [{type_label}] Score: {risk.score:.1f}/10")
                lines.append(f"     Module: {risk.module_name}")
                lines.append(f"     Issue:  {risk.description}")
            
            if len(self.risk_modules) > 15:
                lines.append(f"\n  ... and {len(self.risk_modules) - 15} more at-risk modules")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Priority Actions:
1. Fix CRITICAL circular imports immediately - they cause runtime errors
2. Refactor hub modules - extract functionality to reduce coupling
3. Break heavy modules into smaller, focused components
4. Add lazy imports for type hints (if TYPE_CHECKING:)
5. Consider dependency injection to decouple modules

Prevention:
- Add this script to CI pipeline
- Set maximum import count thresholds per module
- Review new imports in code review
- Use architecture decision records (ADRs) for major changes
""")
        
        return "\n".join(lines)
    
    def generate_dot_graph(self) -> str:
        """Generate Graphviz DOT format for visualization."""
        dot_lines = [
            'digraph ImportGraph {',
            '    rankdir=LR;',
            '    node [shape=box];',
            '    splines=true;',
            '    overlap=false;',
            '',
            '    // Subgraph for circular dependencies',
            '    subgraph cluster_cyclic {',
            '        label="Circular Dependencies";',
            '        style=dashed;',
            '        color=red;',
        ]
        
        # Add nodes and edges for circular deps
        shown_nodes = set()
        for chain in self.chains[:10]:  # Limit for readability
            color = 'red' if chain.severity == 'CRITICAL' else ('orange' if chain.severity == 'WARNING' else 'gray')
            
            for i in range(len(chain.chain) - 1):
                src = chain.chain[i].replace('.', '_')
                dst = chain.chain[i+1].replace('.', '_')
                
                if src not in shown_nodes:
                    dot_lines.append(f'        "{src}" [fillcolor=lightyellow, style=filled];')
                    shown_nodes.add(src)
                if dst not in shown_nodes:
                    dot_lines.append(f'        "{dst}" [fillcolor=lightyellow, style=filled];')
                    shown_nodes.add(dst)
                
                dot_lines.append(f'        "{src}" -> "{dst}" [color={color}, penwidth=2];')
        
        dot_lines.extend([
            '    }',
            '',
            '    // High-risk hub modules',
        ])
        
        # Add hub modules
        for risk in self.risk_modules[:5]:
            if risk.risk_type == 'hub':
                node_id = risk.module_name.replace('.', '_')
                dot_lines.append(f'    "{node_id}" [shape=doublecircle, color=red, fillcolor=lightcoral, style=filled];')
        
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total_modules": len(self.modules),
                "total_imports": len(self.edges),
                "circular_dependencies": len(self.chains),
                "critical_circuits": sum(1 for c in self.chains if c.severity == 'CRITICAL'),
                "warning_circuits": sum(1 for c in self.chains if c.severity == 'WARNING'),
                "high_risk_modules": len(self.risk_modules),
            },
            "circular_chains": [{
                "chain": c.chain,
                "length": c.cycle_length,
                "severity": c.severity,
                "impact": c.impact_description,
                "suggestion": c.suggestion
            } for c in self.chains],
            "risk_modules": [{
                "module": r.module_name,
                "type": r.risk_type,
                "score": r.score,
                "description": r.description,
                "metrics": r.metrics
            } for r in self.risk_modules],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Circular Import Mapper - Detect circular dependencies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python circular_import_mapper.py
  python circular_import_mapper.py --backend-dir ../backend --output-format json
  python circular_import_mapper.py --output-format dot | dot -Tpng -o imports.png
"""
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory (default: ../backend)')
    parser.add_argument('--base-package', default='',
                       help='Base package name for module resolution')
    parser.add_argument('--output-format', '-o', choices=['text', 'json', 'dot'], 
                       default='text', help='Output format')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit with error code if critical issues found')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print(f"🔁 SupremeAI Circular Import Mapper")
    print(f"   Backend: {backend_dir}")
    print()
    
    # Extract imports using AST
    extractor = ASTImportExtractor()
    edges, modules = extractor.extract_from_directory(backend_dir, args.base_package)
    
    # Detect circular dependencies
    detector = CircularDependencyDetector(edges, modules)
    chains = detector.detect_cycles()
    
    # Analyze risks
    analyzer = RiskAnalyzer(modules, edges)
    risk_modules = analyzer.analyze()
    
    # Generate report
    generator = ReportGenerator(chains, risk_modules, modules, edges)
    
    if args.output_format == 'json':
        output = json.dumps(generator.generate_json_report(), indent=2)
    elif args.output_format == 'dot':
        output = generator.generate_dot_graph()
    else:
        output = generator.generate_text_report()
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"✅ Report written to: {args.output_file}")
    else:
        print(output)
    
    # Exit code
    critical_count = sum(1 for c in chains if c.severity == 'CRITICAL')
    if args.fail_on_critical and critical_count > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
