#!/usr/bin/env python3
"""
LLM Cost Projector for SupremeAI
=================================
Scans codebase for LLM API call patterns (max_tokens, model choices)
and generates monthly cost projections.

Features:
- Finds all LLM API calls and their token/parameter settings
- Estimates costs based on model pricing
- Projects monthly costs based on usage patterns
- Identifies cost optimization opportunities

Usage:
    python llm_cost_projector.py [--project-root ../] [--output-format text|json]
    
Pricing data is approximate - update PRICING_DATA as needed.
"""

import re
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


# Approximate pricing per 1K tokens (input/output) - UPDATE THESE REGULARLY!
PRICING_DATA = {
    # OpenAI Models
    'gpt-4o': {'input': 0.0025, 'output': 0.01},
    'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
    'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
    'gpt-4': {'input': 0.03, 'output': 0.06},
    'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
    
    # Anthropic Models
    'claude-sonnet-4-20250514': {'input': 0.003, 'output': 0.015},
    'claude-3-5-sonnet-20241022': {'input': 0.003, 'output': 0.015},
    'claude-3-haiku-20240307': {'input': 0.00025, 'output': 0.00125},
    'claude-3-opus-20240229': {'input': 0.015, 'output': 0.075},
    
    # Google Models
    'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
    'gemini-1.5-flash': {'input': 0.000075, 'output': 0.0003},
    'gemini-pro': {'input': 0.00025, 'output': 0.0005},
    
    # Open Source / Local (approximate hosting cost)
    'llama-3-70b': {'input': 0.0002, 'output': 0.0002},  # Self-hosted
    'mixtral-8x7b': {'input': 0.0001, 'output': 0.0001},
    'codestral': {'input': 0.0002, 'output': 0.0002},
    
    # Default fallback
    'default': {'input': 0.001, 'output': 0.003},
}


@dataclass
class LLMPattern:
    """An LLM usage pattern found in code."""
    model_name: str
    max_tokens: int
    temperature: Optional[float]
    file_path: str
    line_number: int
    context: str  # Surrounding code for identification
    call_type: str  # 'completion', 'chat', 'embedding', 'streaming'
    estimated_calls_per_day: float = 10.0  # Default estimate


@dataclass
class CostProjection:
    """Cost projection for a pattern or aggregate."""
    pattern: LLMPattern
    daily_cost: float
    monthly_cost: float
    yearly_cost: float
    input_tokens_per_call: int = 0
    output_tokens_per_call: int = 0


@dataclass
class OptimizationSuggestion:
    """A suggestion for reducing LLM costs."""
    suggestion_type: str  # 'model_downgrade', 'token_reduction', 'caching', etc.
    location: str
    current_cost: float
    potential_savings: float
    description: str
    implementation: str = ""


class LLMPatternScanner:
    """Scans for LLM usage patterns in code."""
    
    MODEL_PATTERNS = [
        # OpenAI-style
        r'(?:model\s*=\s*["\'])([\w\-\.]+)',
        r'(?:GPT[_\w]*\s*\(\s*.*?model\s*=\s*["\'])([\w\-\.]+)',
        r'(["\'](?:gpt|gpt-\d|gpt-\d[\w\-]*)[\w\-]*["\'])',
        
        # Anthropic-style
        r'(?:anthropic|claude).*?model\s*=\s*["\']([\w\-\.]+)',
        r'(["\']claude[\w\-\.]*["\'])',
        
        # Google-style
        r'(?:genai|gemini).*?model\s*=\s*["\']([\w\-\.]+)',
        r'(["\']gemini[\w\-\.]*["\'])',
        
        # Generic
        r'(?:llm_model|model_name|model_id)\s*=\s*["\']([\w\-\.]+)',
        r'(?:MODEL|MODEL_NAME)\s*=\s*["\']([\w\-\.]+)',
    ]
    
    TOKEN_PATTERNS = [
        r'max_tokens?\s*=\s*(\d+)',
        r'max_completion_tokens?\s*=\s*(\d+)',
        r'max_length\s*=\s*(\d+)',
        r'max_new_tokens\s*=\s*(\d+)',
    ]
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.patterns: List[LLMPattern] = []
        
    def scan(self) -> List[LLMPattern]:
        """Scan all source files for LLM patterns."""
        self._scan_python_files()
        self._scan_typescript_files()
        
        logger.info(f"Found {len(self.patterns)} LLM usage patterns")
        return self.patterns
    
    def _scan_python_files(self):
        """Scan Python files."""
        extensions = ['*.py']
        skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'node_modules'}
        
        for ext in extensions:
            for py_file in self.project_root.rglob(ext):
                if any(skip in str(py_file) for skip in skip_dirs):
                    continue
                self._scan_py_file(py_file)
    
    def _scan_py_file(self, file_path: Path):
        """Scan a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Look for model references
            model_name = None
            max_tokens = None
            temperature = None
            
            for pattern in self.MODEL_PATTERNS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    raw_model = match.group(1).strip('"\'')
                    if raw_model and len(raw_model) > 2:
                        model_name = raw_model.lower()
                        break
            
            if not model_name:
                i += 1
                continue
            
            # Look for token limits in nearby lines (within next 5 lines)
            for j in range(i, min(i + 6, len(lines))):
                for pattern in self.TOKEN_PATTERNS:
                    match = re.search(pattern, lines[j])
                    if match:
                        max_tokens = int(match.group(1))
                        break
                if max_tokens:
                    break
            
            # Look for temperature
            temp_match = re.search(r'temperature\s*=\s*([\d.]+)', line)
            if temp_match:
                temperature = float(temp_match.group(1))
            
            # Determine call type
            call_type = 'completion'
            if any(kw in line.lower() for kw in ['chat', 'conversation']):
                call_type = 'chat'
            elif any(kw in line.lower() for kw in ['embed', 'embedding', 'vector']):
                call_type = 'embedding'
            elif any(kw in line.lower() for kw in ['stream', 'sse', 'async']):
                call_type = 'streaming'
            
            # Estimate calls per day based on context
            est_calls = self._estimate_call_frequency(line, rel_path)
            
            self.patterns.append(LLMPattern(
                model_name=model_name,
                max_tokens=max_tokens or 1000,  # Default
                temperature=temperature,
                file_path=rel_path,
                line_number=i + 1,
                context=line.strip()[:150],
                call_type=call_type,
                estimated_calls_per_day=est_calls
            ))
            
            i += 1
    
    def _scan_typescript_files(self):
        """Scan TypeScript/JavaScript files."""
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        skip_dirs = {'node_modules', 'dist', '.next'}
        
        for ext in extensions:
            for ts_file in self.project_root.rglob(ext):
                if any(skip in str(ts_file) for skip in skip_dirs):
                    continue
                self._scan_ts_file(ts_file)
    
    def _scan_ts_file(self, file_path: Path):
        """Scan a TypeScript/JavaScript file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        for i, line in enumerate(lines):
            # Similar to Python but JS syntax
            model_match = re.search(r'model[:\s]+["\']([\w\-\.]+)["\']', line, re.IGNORECASE)
            if not model_match:
                continue
                
            model_name = model_match.group(1).lower()
            
            token_match = re.search(r'maxTokens?[:\s]+(\d+)', line)
            max_tokens = int(token_match.group(1)) if token_match else 1000
            
            temp_match = re.search(r'temperature[:\s]+([\d.]+)', line)
            temperature = float(temp_match.group(1)) if temp_match else None
            
            est_calls = self._estimate_call_frequency(line, rel_path)
            
            self.patterns.append(LLMPattern(
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                file_path=rel_path,
                line_number=i + 1,
                context=line.strip()[:150],
                call_type='chat',
                estimated_calls_per_day=est_calls
            ))
    
    def _estimate_call_frequency(self, line: str, file_path: str) -> float:
        """Estimate how often this code runs per day."""
        base = 10.0  # Default
        
        # Increase for common endpoints
        if any(p in file_path.lower() for p in ['route', 'api', 'endpoint', 'handler']):
            base *= 10  # API endpoints called more often
        
        if any(p in file_path.lower() for p in ['agent', 'task', 'worker', 'job']):
            base *= 5  # Agent tasks run frequently
        
        if any(p in file_path.lower() for p in ['cron', 'scheduled', 'batch']):
            base *= 20  # Batch jobs process many items
        
        # Decrease for less common paths
        if any(p in file_path.lower() for p in ['admin', 'debug', 'test']):
            base *= 0.5
        
        # Check for loop indicators (might be batch processing)
        if 'for ' in line.lower() or 'while ' in line.lower():
            base *= 5
        
        return base


class CostCalculator:
    """Calculates cost projections."""
    
    def __init__(self, patterns: List[LLMPattern]):
        self.patterns = patterns
        self.projections: List[CostProjection] = []
        self.total_monthly = 0.0
        self.by_model: Dict[str, float] = defaultdict(float)
        
    def calculate(self) -> Tuple[List[CostProjection], float]:
        """Calculate cost projections for all patterns."""
        for pattern in self.patterns:
            proj = self._calculate_pattern(pattern)
            self.projections.append(proj)
            self.total_monthly += proj.monthly_cost
            self.by_model[pattern.model_name] += proj.monthly_cost
        
        return self.projections, self.total_monthly
    
    def _calculate_pattern(self, pattern: LLMPattern) -> CostProjection:
        """Calculate cost projection for a single pattern."""
        # Get pricing for this model
        pricing = PRICING_DATA.get(pattern.model_name, PRICING_DATA['default'])
        
        # Estimate token usage
        # Assume input is ~2x output for chat, ~equal for completion
        if pattern.call_type == 'chat':
            input_tokens = pattern.max_tokens * 2
            output_tokens = pattern.max_tokens
        elif pattern.call_type == 'embedding':
            input_tokens = pattern.max_tokens * 1.5  # Embeddings are usually input-heavy
            output_tokens = 0  # No output tokens for embeddings typically
        else:
            input_tokens = pattern.max_tokens * 1.5
            output_tokens = pattern.max_tokens
        
        # Calculate per-call cost
        input_cost = (input_tokens / 1000) * pricing['input']
        output_cost = (output_tokens / 1000) * pricing['output']
        per_call_cost = input_cost + output_cost
        
        # Project costs
        daily_cost = per_call_cost * pattern.estimated_calls_per_day
        monthly_cost = daily_cost * 30
        yearly_cost = monthly_cost * 12
        
        return CostProjection(
            pattern=pattern,
            daily_cost=daily_cost,
            monthly_cost=monthly_cost,
            yearly_cost=yearly_cost,
            input_tokens_per_call=input_tokens,
            output_tokens_per_call=output_tokens
        )
    
    def get_optimization_suggestions(self) -> List[OptimizationSuggestion]:
        """Generate cost optimization suggestions."""
        suggestions = []
        
        # Group by model to find expensive choices
        model_costs = defaultdict(list)
        for proj in self.projections:
            model_costs[proj.pattern.model_name].append(proj)
        
        for model, projs in model_costs.items():
            total_monthly = sum(p.monthly_cost for p in projs)
            
            # Suggest cheaper alternatives for expensive models
            if 'gpt-4' in model or 'opus' in model:
                cheaper = 'gpt-4o-mini' if 'gpt' in model else 'claude-3-haiku'
                potential_savings = total_monthly * 0.7  # Rough estimate
                
                suggestions.append(OptimizationSuggestion(
                    suggestion_type='model_downgrade',
                    location=', '.join(set(p.pattern.file_path for p in projs)),
                    current_cost=total_monthly,
                    potential_savings=potential_savings,
                    description=f"Consider using {cheaper} instead of {model}",
                    implementation=f"Change model from '{model}' to '{cheaper}' where possible"
                ))
        
        # Find high max_tokens values
        high_token_projs = [p for p in self.projections 
                           if p.pattern.max_tokens > 4000 and p.monthly_cost > 1]
        
        for proj in high_token_projs[:5]:
            reduction = (proj.pattern.max_tokens - 2000) / proj.pattern.max_tokens
            savings = proj.monthly_cost * reduction * 0.5  # Conservative estimate
            
            suggestions.append(OptimizationSuggestion(
                suggestion_type='token_reduction',
                location=f"{proj.pattern.file_path}:{proj.pattern.line_number}",
                current_cost=proj.monthly_cost,
                potential_savings=savings,
                description=f"High max_tokens ({proj.pattern.max_tokens}) at {proj.pattern.file_path}",
                implementation=f"Reduce max_tokens from {proj.pattern.max_tokens} to 2000 or implement chunking"
            ))
        
        # Sort by savings potential
        suggestions.sort(key=lambda s: s.potential_savings, reverse=True)
        
        return suggestions[:10]


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, projections: List[CostProjection], total_monthly: float,
                 by_model: Dict[str, float], suggestions: List[OptimizationSuggestion]):
        self.projections = sorted(projections, key=lambda p: -p.monthly_cost)
        self.total_monthly = total_monthly
        self.by_model = dict(sorted(by_model.items(), key=lambda x: -x[1]))
        self.suggestions = suggestions
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI LLM COST PROJECTION REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Disclaimer
        lines.append("⚠️ DISCLAIMER")
        lines.append("-" * 40)
        lines.append("  These are ESTIMATES based on code analysis.")
        lines.append("  Actual costs depend on runtime usage patterns.")
        lines.append("  Pricing data should be updated regularly.")
        lines.append("")
        
        # Summary
        lines.append("COST SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Estimated Monthly LLM Cost:   ${self.total_monthly:>10,.2f}")
        lines.append(f"  Estimated Yearly LLM Cost:     ${self.total_monthly * 12:>10,.2f}")
        lines.append(f"  LLM Usage Patterns Found:      {len(self.projections):>10}")
        lines.append("")
        
        # By Model Breakdown
        lines.append("\nCOST BY MODEL")
        lines.append("-" * 40)
        lines.append(f"  {'Model':<30} {'Monthly Cost':>15} {'% of Total':>12}")
        lines.append(f"  {'-'*30} {'-'*15} {'-'*12}")
        
        for model, cost in self.by_model.items():
            pct = (cost / self.total_monthly * 100) if self.total_monthly else 0
            lines.append(f"  {model:<30} ${cost:>12,.2f} {pct:>11.1f}%")
        
        # Top Cost Drivers
        lines.append("\n\nTOP 15 COST DRIVERS")
        lines.append("=" * 40)
        
        for i, proj in enumerate(self.projections[:15], 1):
            p = proj.pattern
            lines.append(f"\n  {i}. ${proj.monthly_cost:.2f}/month (${proj.yearly_cost:.0f}/year)")
            lines.append(f"     Model:       {p.model_name}")
            lines.append(f"     Max Tokens:  {p.max_tokens:,}")
            lines.append(f"     Est. Calls/Day: {p.estimated_calls_per_day:.0f}")
            lines.append(f"     Location:    {p.file_path}:{p.line_number}")
            lines.append(f"     Type:        {p.call_type}")
        
        # Optimization Suggestions
        if self.suggestions:
            lines.append("\n\n💰 OPTIMIZATION SUGGESTIONS")
            lines.append("=" * 40)
            lines.append(f"  Total Potential Monthly Savings: "
                       f"${sum(s.potential_savings for s in self.suggestions):,.2f}")
            lines.append("")
            
            for i, sug in enumerate(self.suggestions, 1):
                lines.append(f"\n  {i}. [{sug.suggestion_type}] Save ${sug.potential_savings:.2f}/month")
                lines.append(f"     Current Cost: ${sug.current_cost:.2f}/month")
                lines.append(f"     {sug.description}")
                lines.append(f"     → {sug.implementation}")
        
        # Pricing Reference
        lines.append("\n\n📊 PRICING REFERENCE (per 1K tokens)")
        lines.append("-" * 40)
        lines.append(f"  {'Model':<30} {'Input':>10} {'Output':>10}")
        for model, prices in list(PRICING_DATA.items())[:10]:
            lines.append(f"  {model:<30} ${prices['input']:>9.4f} ${prices['output']:>9.4f}")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total_monthly_usd": round(self.total_monthly, 2),
                "total_yearly_usd": round(self.total_monthly * 12, 2),
                "patterns_analyzed": len(self.projections),
                "potential_monthly_savings": round(
                    sum(s.potential_savings for s in self.suggestions), 2
                ),
            },
            "by_model": {k: round(v, 2) for k, v in self.by_model.items()},
            "top_cost_drivers": [{
                "file": p.pattern.file_path,
                "line": p.pattern.line_number,
                "model": p.pattern.model_name,
                "max_tokens": p.pattern.max_tokens,
                "calls_per_day_est": p.pattern.estimated_calls_per_day,
                "monthly_cost": round(p.monthly_cost, 2),
            } for p in self.projections[:20]],
            "optimization_suggestions": [asdict(s) for s in self.suggestions],
            "pricing_data": PRICING_DATA,
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI LLM Cost Projector - Estimate LLM API costs',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--project-root', '-p', default='..',
                       help='Project root directory')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    project_root = (script_dir / args.project_root).resolve()
    
    print(f"💰 SupremeAI LLM Cost Projector")
    print(f"   Project Root: {project_root}")
    print()
    
    # Scan for patterns
    scanner = LLMPatternScanner(project_root)
    patterns = scanner.scan()
    
    # Calculate costs
    calculator = CostCalculator(patterns)
    projections, total_monthly = calculator.calculate()
    suggestions = calculator.get_optimization_suggestions()
    
    # Generate report
    generator = ReportGenerator(projections, total_monthly, calculator.by_model, suggestions)
    
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
