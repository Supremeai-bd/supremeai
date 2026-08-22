import os
import sys
import json
import re
import argparse
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum
from dataclasses import dataclass

def main():
    parser = argparse.ArgumentParser(
        description='🔍 SuperAI Config Validator - Environment & configuration validation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Full validation
  %(prog)s --security                   # Security-focused check
  %(prog)s --env-only                   # Check only environment variables
  %(prog)s --fix                        # Auto-fix common issues
  %(prog)s --json                       # JSON output for CI/CD
        """
    )
    
    parser.add_argument('--project-root', '-p', type=str, default=None,
                        help='Project root directory')
    parser.add_argument('--security', '-s', action='store_true',
                        help='Security-focused validation only')
    parser.add_argument('--env-only', '-e', action='store_true',
                        help='Check environment variables only')
    parser.add_argument('--fix', '-f', action='store_true',
                        help='Auto-fix common issues')
    parser.add_argument('--json', '-j', action='store_true',
                        help='JSON output format')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    project_root = Path(args.project_root) if args.project_root else None
    
    validator = SuperAIConfigValidator(
        project_root=project_root,
        security_only=args.security,
        env_only=args.env_only,
        auto_fix=args.fix,
        verbose=args.verbose
    )
    
    report = validator.run_all_validations()
    
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        validator.print_report()
    
    # Exit code
    sys.exit(0 if report.is_valid else 1)