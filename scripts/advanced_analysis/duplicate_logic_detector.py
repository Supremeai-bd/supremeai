#!/usr/bin/env python3
"""
Duplicate Logic Detector for SupremeAI
=======================================
Uses AST-level structural similarity to find semantically similar
functions/classes - not just byte-identical code.

Detects:
- Functions with similar structure/logic (different variable names)
- Classes with similar method signatures and bodies
- Copy-pasted code blocks that have been slightly modified
- "Same job, different name" patterns common in large codebases

Usage:
    python duplicate_logic_detector.py [--backend-dir ../backend] [--output-format text|json]
    
Self-healing principles:
- AST-based comparison (not text diff)
- Structural similarity scoring
- Ignores trivial differences (variable names, formatting)
"""

import ast
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Tuple, Optional, Any, Iterator
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodeBlock:
    """A block of code (function, class, or section)."""
    name: str
    type: str  # 'function', 'async_function', 'class', 'method'
    file_path: str
    line_start: int
    line_end: int
    ast_node: Any = None  # The actual AST node
    normalized_ast: str = ""  # Normalized representation for comparison
    signature: str = ""  # Function/class signature
    body_hash: str = ""  # Hash of normalized body
    complexity: int = 0  # Rough complexity estimate


@dataclass
class DuplicatePair:
    """Two code blocks that are suspiciously similar."""
    block_a: CodeBlock
    block_b: CodeBlock
    similarity_score: float  # 0.0 - 1.0
    similarity_type: str  # 'identical', 'structural', 'near_miss'
    shared_structure: List[str] = field(default_factory=list)  # What's similar
    differences: List[str] = field(default_factory=list)  # What's different
    suggestion: str = ""


@dataclass
class DuplicationReport:
    """Summary report of duplication findings."""
    total_blocks_analyzed: int = 0
    duplicate_pairs_found: int = 0
    high_confidence_dups: int = 0  # >90% similar
    medium_confidence_dups: int = 0  # 70-90% similar
    files_with_duplications: int = 0
    estimated_lines_savings: int = 0  # If deduplicated


class ASTNormalizer:
    """Normalizes AST nodes for comparison by removing non-essential details."""
    
    @staticmethod
    def normalize_function(node: ast.AST) -> str:
        """Normalize a function definition for comparison."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result = []
            
            # Normalize signature (parameter count, not names)
            args = node.args
            result.append(f"ARGS:{len(args.args)},defaults:{len(args.defaults)}")
            
            # Add keyword-only args
            if args.kwonlyargs:
                result.append(f"KWONLY:{len(args.kwonlyargs)}")
            
            # Add **kwargs
            if args.kwarg:
                result.append("HAS_KWARGS")
            
            # Normalize body structure
            body_stats = ASTNormalizer._analyze_body(node.body)
            result.extend(body_stats)
            
            return "|".join(result)
        
        return ""
    
    @staticmethod
    def _analyze_body(body: List[ast.stmt]) -> List[str]:
        """Analyze body statements and return structural description."""
        stats = []
        
        for stmt in body:
            if isinstance(stmt, ast.If):
                stats.append("IF")
                # Recursively analyze branches
                stats.extend(ASTNormalizer._analyze_body(stmt.body))
                stats.extend(ASTNormalizer._analyze_body(stmt.orelse))
                
            elif isinstance(stmt, ast.For):
                stats.append("FOR")
                stats.extend(ASTNormalizer._analyze_body(stmt.body))
                stats.extend(ASTNormalizer._analyze_body(stmt.orelse))
                
            elif isinstance(stmt, ast.While):
                stats.append("WHILE")
                stats.extend(ASTNormalizer._analyze_body(stmt.body))
                stats.extend(ASTNormalizer._analyze_body(stmt.orelse))
                
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                stats.append("WITH")
                stats.extend(ASTNormalizer._analyze_body(stmt.body))
                
            elif isinstance(stmt, ast.Try):
                stats.append("TRY")
                stats.extend(ASTNormalizer._analyze_body(stmt.body))
                for handler in stmt.handlers:
                    stats.extend(ASTNormalizer._analyze_body(handler.body))
                stats.extend(ASTNormalizer._analyze_body(stmt.orelse))
                stats.extend(ASTNormalizer._analyze_body(stmt.finalbody))
                
            elif isinstance(stmt, ast.Return):
                stats.append("RETURN")
                
            elif isinstance(stmt, ast.Assign):
                stats.append("ASSIGN")
                
            elif isinstance(stmt, ast.AugAssign):
                stats.append("AUG_ASSIGN")
                
            elif isinstance(stmt, ast.Expr):
                stats.append("EXPR")
                
            elif isinstance(stmt, ast.Raise):
                stats.append("RAISE")
                
            elif isinstance(stmt, ast.Assert):
                stats.append("ASSERT")
                
            elif isinstance(stmt, (ast.Break, ast.Continue, ast.Pass)):
                stats.append(type(stmt).__name__.upper())
        
        return stats
    
    @staticmethod
    def normalize_class(node: ast.ClassDef) -> str:
        """Normalize a class definition."""
        result = [f"BASES:{len(node.bases)}"]
        
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
                result.append(f"METHOD:{ASTNormalizer.normalize_function(item)}")
        
        return "|".join(result)


class CodeExtractor:
    """Extracts code blocks from source files."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.blocks: List[CodeBlock] = []
    
    def extract(self) -> List[CodeBlock]:
        """Extract all code blocks from Python files."""
        py_files = self._find_python_files()
        
        for py_file in py_files:
            self._extract_from_file(py_file)
        
        logger.info(f"Extracted {len(self.blocks)} code blocks from {len(py_files)} files")
        return self.blocks
    
    def _find_python_files(self) -> List[Path]:
        """Find Python files to analyze."""
        skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'dist', 
                    'build', '.tox', 'node_modules', '__pycache__',
                    'migrations'}
        
        py_files = []
        for py_file in self.project_dir.rglob("*.py"):
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            
            # Skip very small files (< 10 lines) - unlikely to have meaningful dups
            try:
                with open(py_file) as f:
                    if len(f.readlines()) < 10:
                        continue
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f"Silenced error: {e}")
                
            py_files.append(py_file)
        
        return py_files
    
    def _extract_from_file(self, file_path: Path):
        """Extract code blocks from a single file."""
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
        
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                block = self._create_block('function', node, lines, rel_path)
                if block:
                    self.blocks.append(block)
                    
            elif isinstance(node, ast.AsyncFunctionDef):
                block = self._create_block('async_function', node, lines, rel_path)
                if block:
                    self.blocks.append(block)
                    
            elif isinstance(node, ast.ClassDef):
                block = self._create_block('class', node, lines, rel_path)
                if block:
                    self.blocks.append(block)
    
    def _create_block(self, block_type: str, node: ast.AST, 
                      lines: List[str], rel_path: str) -> Optional[CodeBlock]:
        """Create a CodeBlock from an AST node."""
        # Get line range
        line_start = getattr(node, 'lineno', 0)
        line_end = getattr(node, 'end_lineno', line_start)
        
        # Get name
        name = getattr(node, 'name', '<anonymous>')
        
        # Create signature string
        signature = self._get_signature(node, lines)
        
        # Normalize for comparison
        if block_type == 'class':
            normalized = ASTNormalizer.normalize_class(node)
        else:
            normalized = ASTNormalizer.normalize_function(node)
        
        # Estimate complexity
        complexity = self._estimate_complexity(node)
        
        return CodeBlock(
            name=name,
            type=block_type,
            file_path=rel_path,
            line_start=line_start,
            line_end=line_end,
            ast_node=node,
            normalized_ast=normalized,
            signature=signature,
            complexity=complexity
        )
    
    def _get_signature(self, node: ast.AST, lines: List[str]) -> str:
        """Get code signature as string."""
        if line_start := getattr(node, 'lineno', 0):
            if line_start <= len(lines):
                return lines[line_start - 1].strip()[:100]
        return ""
    
    def _estimate_complexity(self, node: ast.AST) -> int:
        """Rough complexity estimate based on statement count."""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, 
                                ast.With, ast.ExceptHandler)):
                count += 1
        return count


class DuplicateDetector:
    """Detects duplicate/similar code blocks."""
    
    def __init__(self, blocks: List[CodeBlock]):
        self.blocks = blocks
        self.pairs: List[DuplicatePair] = []
        
        # Index blocks for faster lookup
        self.by_type: Dict[str, List[CodeBlock]] = defaultdict(list)
        for block in blocks:
            self.by_type[block.type].append(block)
    
    def detect(self, threshold: float = 0.7) -> List[DuplicatePair]:
        """Detect duplicate pairs above similarity threshold."""
        comparisons = 0
        
        # Compare within same type first (most likely duplicates)
        for block_type, typed_blocks in self.by_type.items():
            for i, block_a in enumerate(typed_blocks):
                for block_b in typed_blocks[i+1:]:
                    # Skip same-file adjacent functions (likely intentional)
                    if (block_a.file_path == block_b.file_path and 
                        abs(block_a.line_start - block_b.line_start) < 5):
                        continue
                    
                    comparisons += 1
                    pair = self._compare_blocks(block_a, block_b, threshold)
                    if pair:
                        self.pairs.append(pair)
        
        logger.info(f"Performed {comparisons} comparisons, found {len(self.pairs)} potential duplicates")
        return self.pairs
    
    def _compare_blocks(self, a: CodeBlock, b: CodeBlock, 
                       threshold: float) -> Optional[DuplicatePair]:
        """Compare two blocks and return pair if similar enough."""
        # Quick filter: vastly different complexity
        if abs(a.complexity - b.complexity) > max(a.complexity, b.complexity) * 0.8:
            return None
        
        # Method 1: Normalized AST comparison
        ast_similarity = self._normalized_similarity(a.normalized_ast, b.normalized_ast)
        
        # Method 2: Signature comparison
        sig_similarity = self._signature_similarity(a.signature, b.signature)
        
        # Combined score (weighted)
        combined_score = (ast_similarity * 0.7) + (sig_similarity * 0.3)
        
        if combined_score >= threshold:
            # Determine similarity type
            if combined_score >= 0.95:
                sim_type = 'identical'
            elif combined_score >= 0.85:
                sim_type = 'structural'
            else:
                sim_type = 'near_miss'
            
            # Analyze what's similar/different
            shared, diffs = self._analyze_differences(a, b)
            
            # Generate suggestion
            suggestion = self._generate_suggestion(a, b, combined_score)
            
            return DuplicatePair(
                block_a=a,
                block_b=b,
                similarity_score=combined_score,
                similarity_type=sim_type,
                shared_structure=shared,
                differences=diffs,
                suggestion=suggestion
            )
        
        return None
    
    def _normalized_similarity(self, norm_a: str, norm_b: str) -> float:
        """Compare normalized AST representations."""
        if not norm_a or not norm_b:
            return 0.0
        
        # Use sequence matcher on normalized strings
        return SequenceMatcher(None, norm_a, norm_b).ratio()
    
    def _signature_similarity(self, sig_a: str, sig_b: str) -> float:
        """Compare signatures."""
        if not sig_a or not sig_b:
            return 0.5
        
        # Extract parameter patterns
        params_a = set(sig_a.replace(' ', '').split(','))
        params_b = set(sig_b.replace(' ', '').split(','))
        
        if not params_a or not params_b:
            return 0.5
        
        # Count matching parameter types/patterns
        intersection = len(params_a & params_b)
        union = len(params_a | params_b)
        
        return intersection / union if union else 0.0
    
    def _analyze_differences(self, a: CodeBlock, b: CodeBlock) -> Tuple[List[str], List[str]]:
        """Analyze specific similarities and differences."""
        shared = []
        diffs = []
        
        # Check structural elements
        a_parts = set(a.normalized_ast.split('|')) if a.normalized_ast else set()
        b_parts = set(b.normalized_ast.split('|')) if b.normalized_ast else set()
        
        shared_elements = a_parts & b_parts
        for elem in sorted(shared_elements)[:5]:
            shared.append(elem)
        
        # Differences
        only_in_a = a_parts - b_parts
        only_in_b = b_parts - a_parts
        
        if only_in_a:
            diffs.append(f"A has: {', '.join(sorted(only_in_a)[:3])}")
        if only_in_b:
            diffs.append(f"B has: {', '.join(sorted(only_in_b)[:3])}")
        
        # Line count difference
        lines_a = a.line_end - a.line_start
        lines_b = b.line_end - b.line_start
        if abs(lines_a - lines_b) > 3:
            diffs.append(f"Size differs: {lines_a} vs {lines_b} lines")
        
        return shared, diffs
    
    def _generate_suggestion(self, a: CodeBlock, b: CodeBlock, score: float) -> str:
        """Generate refactoring suggestion."""
        if score >= 0.95:
            return "Near-identical code. Consider extracting to shared utility function."
        elif score >= 0.85:
            return "Very similar structure. Look for opportunity to use template pattern or shared base."
        else:
            return "Similar logic detected. Review for potential consolidation."


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, pairs: List[DuplicatePair], blocks: List[CodeBlock]):
        self.pairs = sorted(pairs, key=lambda x: (-x.similarity_score, x.block_a.file_path))
        self.blocks = blocks
        
        # Summary stats
        high_conf = sum(1 for p in pairs if p.similarity_score >= 0.9)
        med_conf = sum(1 for p in pairs if 0.7 <= p.similarity_score < 0.9)
        files_affected = len(set(p.block_a.file_path for p in pairs) | 
                           set(p.block_b.file_path for p in pairs))
        
        # Estimate savings (rough)
        est_savings = sum(
            min(p.block_a.line_end - p.block_a.line_start, 
                p.block_b.line_end - p.block_b.line_start)
            for p in pairs if p.similarity_score >= 0.85
        ) // 2  # Assume we could halve each duplicate
        
        self.report = DuplicationReport(
            total_blocks_analyzed=len(blocks),
            duplicate_pairs_found=len(pairs),
            high_confidence_dups=high_conf,
            medium_confidence_dups=med_conf,
            files_with_duplications=files_affected,
            estimated_lines_savings=est_savings
        )
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI DUPLICATE LOGIC DETECTOR REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Blocks Analyzed:             {self.report.total_blocks_analyzed}")
        lines.append(f"  Duplicate Pairs Found:        {self.report.duplicate_pairs_found}")
        lines.append(f"    High Confidence (>90%):     {self.report.high_confidence_dups}")
        lines.append(f"    Medium Confidence (70-90%): {self.report.medium_confidence_dups}")
        lines.append(f"  Files Affected:              {self.report.files_with_duplications}")
        lines.append(f"  Est. Lines Savings (if fixed): {self.report.estimated_lines_savings}")
        lines.append("")
        
        # High confidence duplicates
        high_pairs = [p for p in self.pairs if p.similarity_score >= 0.9]
        if high_pairs:
            lines.append("\n🔴 HIGH CONFIDENCE DUPLICATES (>90% Similar)")
            lines.append("=" * 40)
            
            for i, pair in enumerate(high_pairs[:20], 1):
                lines.append(f"\n  {i}. [{pair.similarity_score:.1%}] {pair.similarity_type.upper()}")
                lines.append(f"     A: {pair.block_a.name} ({pair.block_a.type})")
                lines.append(f"        {pair.block_a.file_path}:{pair.block_a.line_start}")
                lines.append(f"     B: {pair.block_b.name} ({pair.block_b.type})")
                lines.append(f"        {pair.block_b.file_path}:{pair.block_b.line_start}")
                
                if pair.shared_structure:
                    lines.append(f"     Shared: {', '.join(pair.shared_structure[:3])}")
                
                lines.append(f"     💡 {pair.suggestion}")
            
            if len(high_pairs) > 20:
                lines.append(f"\n  ... and {len(high_pairs) - 20} more high-confidence pairs")
        
        # Medium confidence duplicates
        med_pairs = [p for p in self.pairs if 0.7 <= p.similarity_score < 0.9]
        if med_pairs:
            lines.append(f"\n\n⚠️ MEDIUM CONFIDENCE DUPLICATES (70-90%): {len(med_pairs)} pairs")
            lines.append("-" * 40)
            
            # Group by file for summary
            by_file = defaultdict(list)
            for pair in med_pairs:
                key = f"{pair.block_a.file_path} ↔ {pair.block_b.file_path}"
                by_file[key].append(pair)
            
            for file_pair, pairs in list(by_file.items())[:10]:
                best = max(pairs, key=lambda p: p.similarity_score)
                lines.append(f"  • {file_pair}: {len(pairs)} pairs (best: {best.similarity_score:.1%})")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Immediate Actions:
1. Review HIGH CONFIDENCE duplicates - these are strong candidates for refactoring
2. For near-identical code, extract to shared utility module
3. For similar-but-different code, consider template pattern or strategy pattern

Refactoring Strategies:
- Extract Method: Pull common logic into shared function
- Template Method: Keep structure same, vary specifics via parameters
- Strategy Pattern: Encapsulate varying algorithms in separate classes
- Mixin/Composition: Share behavior through composition

Prevention:
- Add this script to CI pipeline
- Code review checklist item: "check for duplication"
- Regular refactoring sprints focused on DRY violations

Note: Some duplication may be intentional (e.g., different contexts requiring
similar but independent implementations). Use judgment when deciding what to refactor.
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": asdict(self.report),
            "duplicates": [{
                "block_a": {
                    "name": p.block_a.name,
                    "type": p.block_a.type,
                    "file": p.block_a.file_path,
                    "line": p.block_a.line_start
                },
                "block_b": {
                    "name": p.block_b.name,
                    "type": p.block_b.type,
                    "file": p.block_b.file_path,
                    "line": p.block_b.line_start
                },
                "similarity": round(p.similarity_score, 3),
                "type": p.similarity_type,
                "suggestion": p.suggestion
            } for p in self.pairs],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Duplicate Logic Detector - Find semantically similar code',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory (default: ../backend)')
    parser.add_argument('--threshold', '-t', type=float, default=0.7,
                       help='Similarity threshold (default: 0.7)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print(f"🔍 SupremeAI Duplicate Logic Detector")
    print(f"   Backend:  {backend_dir}")
    print(f"   Threshold: {args.threshold}")
    print()
    
    # Extract code blocks
    extractor = CodeExtractor(backend_dir)
    blocks = extractor.extract()
    
    # Detect duplicates
    detector = DuplicateDetector(blocks)
    pairs = detector.detect(threshold=args.threshold)
    
    # Generate report
    generator = ReportGenerator(pairs, blocks)
    
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
