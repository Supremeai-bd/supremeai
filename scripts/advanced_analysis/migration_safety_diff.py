#!/usr/bin/env python3
"""
Migration Safety Diff Checker for SupremeAI
============================================
Analyzes Alembic/SQL migrations for potentially destructive operations.

Detects:
- DROP TABLE statements (data loss risk)
- DROP COLUMN statements (data loss risk)
- ALTER TABLE ... DROP CONSTRAINT
- TRUNCATE statements
- Operations on production-critical tables without safeguards

Usage:
    python migration_safety_diff.py [--migrations-dir ../backend/database/migrations]
    
Self-healing principles:
- Auto-discovers migration files
- No hardcoded table lists - uses heuristics for criticality
- CI-friendly with exit codes
"""

import argparse
import json
import logging
import re
import sys
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
class MigrationFile:
    """Represents a database migration file."""
    filename: str
    file_path: str
    revision_id: str  # Alembic revision ID if present
    down_revision: str | None = None
    is_upgrade: bool = True  # upgrade() vs downgrade()
    content: str = ""
    line_count: int = 0


@dataclass 
class DestructiveOperation:
    """A potentially destructive operation found in a migration."""
    op_type: str  # 'DROP_TABLE', 'DROP_COLUMN', 'TRUNCATE', 'DROP_CONSTRAINT', etc.
    target: str  # Table/column being affected
    file_path: str
    line_number: int
    line_content: str
    risk_level: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    has_safeguard: bool = False  # IF EXISTS, CASCADE with backup, etc.
    has_backup_hint: bool = False  # Comment about backup
    suggestion: str = ""


@dataclass
class MigrationSafetyReport:
    """Summary of migration safety analysis."""
    total_migrations: int = 0
    destructive_ops_found: int = 0
    critical_risk_count: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    safe_migrations: int = 0
    tables_affected: list[str] = field(default_factory=list)


# Patterns for destructive operations
DESTRUCTIVE_PATTERNS = [
    # DROP TABLE
    (r'DROP\s+TABLE(?:\s+IF\s+EXISTS)?\s+(?:`?"?(\w+)`"?|PUBLIC\.\w+\."(\w+))', 
     'DROP_TABLE', 'CRITICAL'),
    
    # DROP COLUMN
    (r'DROP\s+COLUMN(?:\s+IF\s+EXISTS)?\s+(?:`?"?(\w+)`"?|\w+\.`?"?(\w+)"?)',
     'DROP_COLUMN', 'HIGH'),
    
    # ALTER TABLE DROP
    (r'ALTER\s+TABLE\s+\w+\.?\s*\w*\s*DROP\s+(?:COLUMN|CONSTRAINT|INDEX)',
     'ALTER_DROP', 'HIGH'),
    
    # TRUNCATE
    (r'TRUNCATE\s+(?:TABLE\s+)?(?:`?"?(\w+)`"?)',
     'TRUNCATE', 'CRITICAL'),
    
    # DELETE without WHERE (full table clear)
    (r'DELETE\s+FROM\s+(\w+)\s*;?\s*$',
     'DELETE_ALL', 'HIGH'),
    
    # DROP INDEX
    (r'DROP\s+INDEX(?:\s+IF\s+EXISTS)?\s*(?:`?"?(\w+)`"?)',
     'DROP_INDEX', 'MEDIUM'),
    
    # DROP SCHEMA
    (r'DROP\s+SCHEMA(?:\s+IF\s+EXISTS)?\s*(?:`?"?(\w+)`"?)',
     'DROP_SCHEMA', 'CRITICAL'),
]

# Patterns that indicate safeguards exist
SAFEGUARD_PATTERNS = [
    r'IF\s+EXISTS',
    r'CASCADE',
    r'--\s*.*(?:backup|safe|confirm|destructive)',
    r'#\s*.*(?:backup|safe|confirm|destructive)',
    r'op\.execute\(f["\'].*DROP.*IF EXISTS',
]

# Tables that are extra-sensitive (user data, payments, etc.)
CRITICAL_TABLE_PATTERNS = [
    r'user', r'account', r'profile', r'password',
    r'payment', r'billing', r'subscription', r'transaction', r'invoice',
    r'session', r'token', r'auth', r'credential', r'secret',
    r'message', r'conversation', r'chat',
    r'api_key', r'key',
]


class MigrationScanner:
    """Scans migration files for destructive operations."""
    
    def __init__(self, migrations_dir: Path):
        self.migrations_dir = Path(migrations_dir)
        self.migrations: list[MigrationFile] = []
        
    def scan(self) -> list[MigrationFile]:
        """Scan all migration files."""
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return []
        
        # Find SQL migrations
        sql_files = sorted(self.migrations_dir.glob("*.sql"))
        
        # Find Python/Alembic migrations
        py_files = sorted(self.migrations_dir.rglob("*.py"))
        py_files = [f for f in py_files if any(p in str(f) for p in ['versions', 'migrations'])]
        
        for sql_file in sql_files:
            self._parse_sql_migration(sql_file)
        
        for py_file in py_files:
            self._parse_python_migration(py_file)
        
        logger.info(f"Found {len(self.migrations)} migration files")
        return self.migrations
    
    def _parse_sql_migration(self, file_path: Path):
        """Parse a SQL migration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.migrations_dir.parent))
        
        migration = MigrationFile(
            filename=file_path.name,
            file_path=rel_path,
            content=content,
            line_count=len(lines)
        )
        
        # Try to extract revision ID from filename or content
        rev_match = re.search(r'revision[\s_=]+([a-f0-9]+)', content[:500], re.IGNORECASE)
        if rev_match:
            migration.revision_id = rev_match.group(1)
        
        self.migrations.append(migration)
    
    def _parse_python_migration(self, file_path: Path):
        """Parse a Python/Alembic migration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.migrations_dir.parent))
        
        # Extract revision info
        revision_id = ''
        down_rev = None
        
        rev_match = re.search(r'revision\s*=\s*[\'"]([^\'"]+)[\'"]', content)
        if rev_match:
            revision_id = rev_match.group(1)
        
        down_match = re.search(r'down_revision\s*=\s*[\'"]([^\'"]*)[\'"]', content)
        if down_match:
            down_rev = down_match.group(1)
        
        migration = MigrationFile(
            filename=file_path.name,
            file_path=rel_path,
            revision_id=revision_id,
            down_revision=down_rev,
            content=content,
            line_count=len(lines)
        )
        
        self.migrations.append(migration)


class SafetyAnalyzer:
    """Analyzes migrations for safety issues."""
    
    def __init__(self, migrations: list[MigrationFile]):
        self.migrations = migrations
        self.destructive_ops: list[DestructiveOperation] = []
        self.report = MigrationSafetyReport(total_migrations=len(migrations))
        
    def analyze(self) -> tuple[list[DestructiveOperation], MigrationSafetyReport]:
        """Perform safety analysis."""
        for migration in self.migrations:
            ops = self._analyze_migration(migration)
            self.destructive_ops.extend(ops)
            
            if not ops:
                self.report.safe_migrations += 1
        
        # Calculate summary stats
        self.report.destructive_ops_found = len(self.destructive_ops)
        self.report.critical_risk_count = sum(1 for o in self.destructive_ops if o.risk_level == 'CRITICAL')
        self.report.high_risk_count = sum(1 for o in self.destructive_ops if o.risk_level == 'HIGH')
        self.report.medium_risk_count = sum(1 for o in self.destructive_ops if o.risk_level == 'MEDIUM')
        self.report.tables_affected = list({o.target for o in self.destructive_ops if o.target})
        
        return self.destructive_ops, self.report
    
    def _analyze_migration(self, migration: MigrationFile) -> list[DestructiveOperation]:
        """Analyze a single migration for destructive operations."""
        ops = []
        lines = migration.content.split('\n')
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments
            if stripped.startswith(('--', '#')):
                continue
            
            # Check each destructive pattern
            for pattern, op_type, base_risk in DESTRUCTIVE_PATTERNS:
                match = re.search(pattern, stripped, re.IGNORECASE)
                if match:
                    target = match.group(1) or match.group(2) if match.lastindex >= 2 else match.group(1) if match else "unknown"
                    
                    # Adjust risk based on target table
                    risk = base_risk
                    if target and target != "unknown":
                        for crit_pattern in CRITICAL_TABLE_PATTERNS:
                            if re.search(crit_pattern, target, re.IGNORECASE):
                                if risk != 'CRITICAL':
                                    risk = 'HIGH'
                                break
                    
                    # Check for safeguards
                    has_safeguard = any(re.search(sg, stripped, re.IGNORECASE) for sg in SAFEGUARD_PATTERNS)
                    
                    # Check nearby comments for backup hints
                    has_backup = False
                    for j in range(max(0, i-5), min(i+2, len(lines))):
                        if re.search(r'(backup|snapshot|copy|archive)', lines[j], re.IGNORECASE):
                            has_backup = True
                            break
                    
                    # Generate suggestion
                    suggestion = self._generate_suggestion(op_type, target, has_safeguard, has_backup)
                    
                    op = DestructiveOperation(
                        op_type=op_type,
                        target=target,
                        file_path=migration.file_path,
                        line_number=i + 1,
                        line_content=stripped[:120],
                        risk_level=risk,
                        has_safeguard=has_safeguard,
                        has_backup_hint=has_backup,
                        suggestion=suggestion
                    )
                    
                    ops.append(op)
        
        return ops
    
    def _generate_suggestion(self, op_type: str, target: str, 
                           has_safeguard: bool, has_backup: bool) -> str:
        """Generate improvement suggestion."""
        suggestions = {
            'DROP_TABLE': (
                f"Consider archiving table '{target}' before dropping. "
                "Use CREATE TABLE ... AS SELECT to backup data first."
            ),
            'DROP_COLUMN': (
                f"Verify column '{target}' is unused. "
                "Consider renaming instead of dropping initially."
            ),
            'TRUNCATE': (
                f"TRUNCATE on '{target}' is irreversible. "
                "Ensure this is intentional and data can be restored."
            ),
            'DELETE_ALL': (
                f"DELETE all from '{target}' without WHERE clause. "
                "Add WHERE condition or use TRUNCATE explicitly."
            ),
            'DROP_INDEX': (
                "Verify index isn't needed for performance. "
                "Check query plans before dropping."
            ),
            'DROP_SCHEMA': (
                "Dropping schema affects multiple tables. "
                "Verify all contents are archived."
            ),
            'ALTER_DROP': (
                "ALTER TABLE DROP operations can break dependent code. "
                "Check for references before executing."
            ),
        }
        
        base = suggestions.get(op_type, "Review this operation carefully.")
        
        if not has_safeguard and not has_backup:
            base += " Add IF EXISTS safeguard and document backup strategy."
        elif not has_backup:
            base += " Consider adding backup step before this operation."
        
        return base


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, ops: list[DestructiveOperation], report: MigrationSafetyReport):
        self.ops = sorted(ops, key=lambda o: (
            {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}.get(o.risk_level, 4),
            o.file_path,
            o.line_number
        ))
        self.report = report
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI MIGRATION SAFETY DIFF REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Migrations Analyzed:         {self.report.total_migrations}")
        lines.append(f"  Safe Migrations:             {self.report.safe_migrations}")
        lines.append(f"  Destructive Ops Found:       {self.report.destructive_ops_found}")
        lines.append(f"    🔴 Critical Risk:          {self.report.critical_risk_count}")
        lines.append(f"    🟠 High Risk:              {self.report.high_risk_count}")
        lines.append(f"    🟡 Medium Risk:            {self.report.medium_risk_count}")
        
        if self.report.tables_affected:
            lines.append(f"\n  Tables Affected:             {', '.join(self.report.tables_affected[:10])}")
            if len(self.report.tables_affected) > 10:
                lines.append(f"                              ...and {len(self.report.tables_affected)-10} more")
        lines.append("")
        
        # Detailed findings
        if self.ops:
            lines.append("\n⚠️ DESTRUCTIVE OPERATIONS DETECTED")
            lines.append("=" * 40)
            
            for i, op in enumerate(self.ops[:30], 1):
                risk_icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(op.risk_level, '⚪')
                
                safe_marker = ""
                if op.has_safeguard:
                    safe_marker = " [HAS SAFEGUARD]"
                if op.has_backup_hint:
                    safe_marker += " [BACKUP MENTIONED]"
                
                lines.append(f"\n  {i}. {risk_icon} [{op.risk_level}] {op.op_type}{safe_marker}")
                lines.append(f"     Target:   {op.target}")
                lines.append(f"     Location: {op.file_path}:{op.line_number}")
                lines.append(f"     Code:     {op.line_content}")
                lines.append(f"     💡 {op.suggestion}")
            
            if len(self.ops) > 30:
                lines.append(f"\n  ... and {len(self.ops) - 30} more operations")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Before Running Destructive Migrations:

1. **Backup First**
   - Always create a snapshot/backup before running
   - For major changes, test on staging first

2. **Add Safeguards**
   - Use IF EXISTS to prevent errors
   - Wrap in transactions where possible
   - Add confirmation prompts for manual runs

3. **Document Intent**
   - Add comments explaining WHY the operation is needed
   - Reference related tickets/issues
   - Note expected impact

4. **Review Process**
   - Require code review for any migration with DROP/TRUNCATE
   - Run this script in CI pipeline
   - Block deployments with unreviewed destructive ops

5. **Rollback Plan**
   - Always have a rollback migration ready
   - Test rollback procedure
   - Document recovery steps

CI Integration:
  Add to your pipeline:
    python migration_safety_diff.py --fail-on-critical
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": asdict(self.report),
            "operations": [asdict(o) for o in self.ops],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Migration Safety Diff Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--migrations-dir', '-m', 
                       default='../backend/database/migrations',
                       help='Migrations directory')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit error if critical operations found')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    migrations_dir = (script_dir / args.migrations_dir).resolve()
    
    print("🛡️ SupremeAI Migration Safety Diff Checker")
    print(f"   Migrations Dir: {migrations_dir}")
    print()
    
    # Scan migrations
    scanner = MigrationScanner(migrations_dir)
    migrations = scanner.scan()
    
    # Analyze safety
    analyzer = SafetyAnalyzer(migrations)
    ops, report = analyzer.analyze()
    
    # Generate report
    generator = ReportGenerator(ops, report)
    
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
    if args.fail_on_critical and report.critical_risk_count > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
