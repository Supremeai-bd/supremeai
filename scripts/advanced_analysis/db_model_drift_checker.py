#!/usr/bin/env python3
"""
Database Model Drift Checker for SupremeAI
============================================
Compares SQLAlchemy/Pydantic models against actual database schema
(migration history) to detect drift.

Detects:
- Models with fields that don't have corresponding DB columns
- Columns in DB without model fields (orphan columns)
- Missing migrations
- Type mismatches between models and schema

Usage:
    python db_model_drift_checker.py [--backend-dir ../backend] [--migrations-dir ./migrations]
    
Self-healing principles:
- Auto-discovers models and migrations
- No hardcoded table/column names
- CI-friendly output
"""

import argparse
import ast
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ModelField:
    """Represents a field in a SQLAlchemy/Pydantic model."""
    name: str
    field_type: str  # String, Integer, JSON, etc.
    nullable: bool = True
    has_default: bool = False
    is_primary_key: bool = False
    is_unique: bool = False
    indexed: bool = False
    model_name: str = ""
    file_path: str = ""
    line_number: int = 0


@dataclass 
class ORMModel:
    """Represents an ORM model definition."""
    name: str
    table_name: str
    file_path: str
    line_number: int
    fields: list[ModelField] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    is_abstract: bool = False
    is_mixin: bool = False


@dataclass
class ColumnDefinition:
    """Represents a database column from migration/schema."""
    name: str
    column_type: str
    nullable: bool = True
    has_default: bool = False
    is_primary_key: bool = False
    table_name: str = ""
    source_file: str = ""
    source_type: str = ""  # migration, schema dump, etc.


@dataclass
class DriftIssue:
    """Represents a drift issue between models and schema."""
    severity: str  # CRITICAL, WARNING, INFO
    drift_type: str
    description: str
    model_name: str | None
    table_name: str | None
    field_name: str | None
    column_name: str | None
    suggestion: str
    model_location: str | None = None
    schema_location: str | None = None


class SQLAlchemyModelExtractor:
    """Extracts ORM model definitions from Python code."""
    
    # Common base classes for SQLAlchemy models
    ORM_BASE_CLASSES = {
        'Base', 'Model', 'DeclarativeBase', 'AsyncBase',
        'TimeStampedModel', 'SoftDeleteMixin', 'id',
        'db.Model', 'SQLAlchemyModel'
    }
    
    # Column type mappings
    TYPE_MAP = {
        'String': 'VARCHAR', 'Text': 'TEXT', 'Integer': 'INTEGER',
        'Float': 'FLOAT', 'Boolean': 'BOOLEAN', 'DateTime': 'TIMESTAMP',
        'Date': 'DATE', 'Time': 'TIME', 'LargeBinary': 'BLOB',
        'JSON': 'JSON', 'JSONB': 'JSONB', 'Numeric': 'NUMERIC',
        'BigInteger': 'BIGINT', 'SmallInteger': 'SMALLINT',
        'Unicode': 'VARCHAR', 'UnicodeText': 'TEXT',
        'ARRAY': 'ARRAY', 'UUID': 'UUID', 'Inet': 'INET',
    }
    
    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.models: list[ORMModel] = []
        
    def extract_models(self) -> list[ORMModel]:
        """Extract all ORM models from the codebase."""
        py_files = list(self.backend_dir.rglob("*.py"))
        
        skip_dirs = {'__pycache__', 'migrations', 'tests', '.git', 
                    'venv', '.venv', 'alembic'}
        
        for py_file in py_files:
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            self._extract_from_file(py_file)
            
        logger.info(f"Extracted {len(self.models)} ORM models")
        return self.models
    
    def _extract_from_file(self, file_path: Path):
        """Extract models from a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return
        
        rel_path = str(file_path.relative_to(self.backend_dir.parent))
        
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            
            # Check if this looks like an ORM model
            base_names = [self._get_class_name(base) for base in node.bases]
            is_orm_model = any(
                base in self.ORM_BASE_CLASSES or 
                'Model' in base or 
                'Declarative' in base
                for base in base_names
            )
            
            # Also check for __tablename__ attribute
            has_tablename = any(
                isinstance(item, ast.Assign) and 
                any(t.id == '__tablename__' for t in item.targets if isinstance(t, ast.Name))
                for item in node.body
            )
            
            if is_orm_model or has_tablename:
                # Check for abstract/mixin patterns
                is_abstract = any(
                    isinstance(item, ast.Assign) and
                    any(getattr(t, 'id', '') == '__abstract__' for t in getattr(item, 'targets', []))
                    for item in node.body
                )
                is_mixin = 'Mixin' in node.name or 'mixins' in rel_path.lower()
                
                # Extract table name
                table_name = self._extract_table_name(node) or node.name.lower()
                
                # Extract fields
                fields = self._extract_fields(node, lines)
                
                self.models.append(ORMModel(
                    name=node.name,
                    table_name=table_name,
                    file_path=rel_path,
                    line_number=node.lineno,
                    fields=fields,
                    base_classes=base_names,
                    is_abstract=is_abstract,
                    is_mixin=is_mixin
                ))
    
    def _get_class_name(self, node: ast.AST) -> str:
        """Get class name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_class_name(node.value)
        return ""
    
    def _extract_table_name(self, class_node: ast.ClassDef) -> str | None:
        """Extract __tablename__ from class."""
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == '__tablename__':
                        if isinstance(item.value, ast.Constant):
                            return item.value.value
                        elif isinstance(item.value, ast.Str):  # Python < 3.8
                            return item.value.s
        return None
    
    def _extract_fields(self, class_node: ast.ClassDef, lines: list[str]) -> list[ModelField]:
        """Extract field definitions from class."""
        fields = []
        model_name = class_node.name
        
        for item in class_node.body:
            # Handle simple assignments: id = Column(Integer, primary_key=True)
            if isinstance(item, ast.Assign):
                field = self._parse_field_assignment(item, model_name, lines)
                if field:
                    fields.append(field)
            
            # Handle annotated assignments: name: Mapped[str] = mapped_column(...)
            elif isinstance(item, ast.AnnAssign):
                field = self._parse_annotated_assignment(item, model_name, lines)
                if field:
                    fields.append(field)
        
        return fields
    
    def _parse_field_assignment(self, assign: ast.Assign, model_name: str, 
                                lines: list[str]) -> ModelField | None:
        """Parse a regular assignment as a field definition."""
        # Get field name
        target = assign.targets[0] if assign.targets else None
        if not isinstance(target, ast.Name):
            return None
        
        field_name = target.id
        value = assign.value
        
        # Check if it's a Column definition
        col_info = self._analyze_column_call(value)
        if col_info:
            return ModelField(
                name=field_name,
                field_type=col_info.get('type', 'Unknown'),
                nullable=col_info.get('nullable', True),
                has_default=col_info.get('has_default', False),
                is_primary_key=col_info.get('is_primary_key', False),
                is_unique=col_info.get('is_unique', False),
                indexed=col_info.get('indexed', False),
                model_name=model_name,
                file_path="",  # Will be set by parent
                line_number=assign.lineno
            )
        
        # Check for relationship() calls - skip these
        if isinstance(value, ast.Call):
            func_name = self._get_func_name(value.func)
            if func_name in ('relationship', 'backref'):
                return None
        
        # It might be a foreign key reference or other non-column
        return None
    
    def _parse_annotated_assignment(self, ann_assign: ast.AnnAssign, 
                                    model_name: str, lines: list[str]) -> ModelField | None:
        """Parse an annotated assignment (SQLAlchemy 2.0 style)."""
        target = ann_assign.target
        if not isinstance(target, ast.Name):
            return None
        
        field_name = target.id
        value = ann_assign.value
        
        if value is None:
            return None
        
        col_info = self._analyze_column_call(value)
        if col_info:
            return ModelField(
                name=field_name,
                field_type=col_info.get('type', 'Unknown'),
                nullable=col_info.get('nullable', True),
                has_default=col_info.get('has_default', False),
                is_primary_key=col_info.get('is_primary_key', False),
                is_unique=col_info.get('is_unique', False),
                indexed=col_info.get('indexed', False),
                model_name=model_name,
                line_number=ann_assign.lineno
            )
        
        return None
    
    def _analyze_column_call(self, node: ast.AST) -> dict[str, Any] | None:
        """Analyze a Column()/mapped_column() call."""
        if not isinstance(node, ast.Call):
            return None
        
        func_name = self._get_func_name(node.func)
        if func_name not in ('Column', 'column', 'mapped_column'):
            return None
        
        result = {
            'type': 'Unknown',
            'nullable': True,
            'has_default': False,
            'is_primary_key': False,
            'is_unique': False,
            'indexed': False
        }
        
        # First argument is usually the type
        if node.args:
            type_arg = node.args[0]
            if isinstance(type_arg, ast.Name):
                result['type'] = self.TYPE_MAP.get(type_arg.id, type_arg.id)
            elif isinstance(type_arg, ast.Attribute):
                result['type'] = self.TYPE_MAP.get(type_arg.attr, type_arg.attr)
        
        # Keyword arguments
        for kw in node.keywords:
            arg_name = kw.arg.lower() if kw.arg else ''
            
            if arg_name == 'primary_key':
                result['is_primary_key'] = self._get_bool_value(kw.value)
            elif arg_name == 'nullable':
                result['nullable'] = self._get_bool_value(kw.value)
            elif arg_name == 'unique':
                result['is_unique'] = self._get_bool_value(kw.value)
            elif arg_name == 'index':
                result['indexed'] = self._get_bool_value(kw.value)
            elif arg_name in ('default', 'server_default'):
                result['has_default'] = True
        
        return result
    
    def _get_func_name(self, node: ast.AST) -> str:
        """Get function name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
    
    def _get_bool_value(self, node: ast.AST) -> bool:
        """Get boolean value from AST node."""
        if isinstance(node, (ast.Constant, ast.NameConstant)):
            return bool(node.value)
        return True  # Default for presence of keyword


class MigrationSchemaExtractor:
    """Extracts schema information from migration files."""
    
    def __init__(self, migrations_dir: Path):
        self.migrations_dir = Path(migrations_dir)
        self.columns: dict[str, list[ColumnDefinition]] = defaultdict(list)  # table_name -> columns
        self.tables: set[str] = set()
        
    def extract_schema(self) -> dict[str, list[ColumnDefinition]]:
        """Extract schema from all migration files."""
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return {}
        
        # Find all SQL migration files
        sql_files = sorted(self.migrations_dir.glob("*.sql"))
        
        # Also check for Alembic Python migrations
        py_files = sorted(self.migrations_dir.rglob("*.py"))
        
        for sql_file in sql_files:
            self._parse_sql_migration(sql_file)
        
        for py_file in py_files:
            if 'versions' in str(py_file) or 'migrations' in str(py_file):
                self._parse_alembic_migration(py_file)
        
        logger.info(f"Extracted schema for {len(self.tables)} tables from {len(sql_files) + len(py_files)} migrations")
        return dict(self.columns)
    
    def _parse_sql_migration(self, file_path: Path):
        """Parse SQL migration file for CREATE TABLE statements."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        # Parse CREATE TABLE statements
        create_pattern = re.compile(
            r'CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+[`"]?(\w+)[`"]?\s*\(([^;]+)\)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in create_pattern.finditer(content):
            table_name = match.group(1).lower()
            columns_str = match.group(2)
            
            self.tables.add(table_name)
            
            # Parse individual columns
            # Split by comma but respect parentheses
            col_parts = self._split_columns(columns_str)
            
            for col_part in col_parts:
                col_part = col_part.strip()
                if not col_part or col_part.upper().startswith(('PRIMARY KEY', 'FOREIGN KEY', 
                                                              'UNIQUE', 'CHECK', 'CONSTRAINT')):
                    continue
                
                col_match = re.match(r'[`"]?(\w+)[`"]?\s+(\w+)(?:\s*\([^)]+\))?', col_part, re.IGNORECASE)
                if col_match:
                    col_name = col_match.group(1)
                    col_type = col_match.group(2).upper()
                    
                    nullable = True
                    if 'NOT NULL' in col_part.upper():
                        nullable = False
                    
                    has_default = 'DEFAULT' in col_part.upper()
                    is_primary = 'PRIMARY' in col_part.upper()
                    
                    self.columns[table_name].append(ColumnDefinition(
                        name=col_name,
                        column_type=col_type,
                        nullable=nullable,
                        has_default=has_default,
                        is_primary_key=is_primary,
                        table_name=table_name,
                        source_file=str(file_path),
                        source_type='sql_migration'
                    ))
    
    def _parse_alembic_migration(self, file_path: Path):
        """Parse Alembic Python migration for op.create_table() calls."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return
        
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return
        
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            
            func_name = self._get_call_name(node.func)
            if func_name not in ('create_table', 'add_column'):
                continue
            
            if func_name == 'create_table':
                table_name = self._get_first_string_arg(node)
                if not table_name:
                    continue
                
                table_name = table_name.lower()
                self.tables.add(table_name)
                
                # Look for Column() arguments
                if len(node.args) > 1:
                    for arg in node.args[1:]:
                        if isinstance(arg, ast.Call):
                            col_def = self._parse_column_call(arg, table_name, file_path)
                            if col_def:
                                self.columns[table_name].append(col_def)
            
            elif func_name == 'add_column':
                # First string arg is table name, second is column
                if len(node.args) >= 2:
                    table_name = self._get_string_value(node.args[0])
                    if table_name:
                        table_name = table_name.lower()
                        self.tables.add(table_name)
                        
                        if isinstance(node.args[1], ast.Call):
                            col_def = self._parse_column_call(node.args[1], table_name, file_path)
                            if col_def:
                                self.columns[table_name].append(col_def)
    
    def _parse_column_call(self, call: ast.Call, table_name: str, 
                           file_path: Path) -> ColumnDefinition | None:
        """Parse a sa.Column() call in Alembic migration."""
        func_name = self._get_call_name(call.func)
        if func_name != 'Column' and func_name != 'column':
            return None
        
        col_name = None
        col_type = 'UNKNOWN'
        nullable = True
        has_default = False
        is_primary = False
        
        if call.args:
            # First arg might be column name (string) or type
            first_arg = call.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                col_name = first_arg.value
            elif isinstance(first_arg, ast.Name):
                col_type = first_arg.id
                
            # Second arg might be type if first was name
            if len(call.args) > 1 and col_name:
                second_arg = call.args[1]
                if isinstance(second_arg, ast.Name):
                    col_type = second_arg.id
        
        for kw in call.keywords:
            if kw.arg == 'nullable':
                nullable = self._get_ast_bool(kw.value)
            elif kw.arg in ('primary_key', 'primary'):
                is_primary = self._get_ast_bool(kw.value)
            elif kw.arg in ('default', 'server_default'):
                has_default = True
        
        if col_name:
            return ColumnDefinition(
                name=col_name,
                column_type=col_type.upper(),
                nullable=nullable,
                has_default=has_default,
                is_primary_key=is_primary,
                table_name=table_name,
                source_file=str(file_path),
                source_type='alembic_migration'
            )
        return None
    
    def _split_columns(self, columns_str: str) -> list[str]:
        """Split column definitions respecting parentheses."""
        parts = []
        current = []
        depth = 0
        
        for char in columns_str:
            if char == '(':
                depth += 1
                current.append(char)
            elif char == ')':
                depth -= 1
                current.append(char)
            elif char == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    def _get_call_name(self, node: ast.AST) -> str:
        """Get function/method call name."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
    
    def _get_first_string_arg(self, call: ast.Call) -> str | None:
        """Get first string argument from call."""
        for arg in call.args:
            val = self._get_string_value(arg)
            if val:
                return val
        return None
    
    def _get_string_value(self, node: ast.AST) -> str | None:
        """Get string value from AST node."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        return None
    
    def _get_ast_bool(self, node: ast.AST) -> bool:
        """Get boolean value from AST node."""
        if isinstance(node, ast.Constant):
            return bool(node.value)
        return True


class DriftChecker:
    """Main checker that compares models to schema."""
    
    def __init__(self, models: list[ORMModel], schema: dict[str, list[ColumnDefinition]]):
        self.models = [m for m in models if not m.is_abstract and not m.is_mixin]
        self.schema = schema
        self.issues: list[DriftIssue] = []
        
        # Build lookup: table_name -> model
        self.model_map: dict[str, ORMModel] = {}
        for model in self.models:
            self.model_map[model.table_name] = model
    
    def check(self) -> list[DriftIssue]:
        """Perform drift detection."""
        self._check_missing_tables()
        self._check_missing_columns()
        self._check_orphan_columns()
        self._check_type_mismatches()
        self._check_nullable_mismatches()
        
        return self.issues
    
    def _check_missing_tables(self):
        """Find models without corresponding tables."""
        for model in self.models:
            if model.table_name not in self.schema:
                # Might be created dynamically or through inheritance
                self.issues.append(DriftIssue(
                    severity='WARNING',
                    drift_type='MISSING_TABLE',
                    description=f"Model '{model.name}' maps to table '{model.table_name}' but no CREATE TABLE found",
                    model_name=model.name,
                    table_name=model.table_name,
                    field_name=None,
                    column_name=None,
                    suggestion=f"Create migration for table '{model.table_name}' or verify dynamic creation",
                    model_location=f"{model.file_path}:{model.line_number}"
                ))
    
    def _check_missing_columns(self):
        """Find model fields without corresponding DB columns."""
        for model in self.models:
            if model.table_name not in self.schema:
                continue
            
            db_columns = {c.name.lower(): c for c in self.schema[model.table_name]}
            
            for field in model.fields:
                if field.name.lower() not in db_columns:
                    # Skip common auto-managed fields
                    if field.name.lower() in ('metadata', 'registry', '_sa_instance_state'):
                        continue
                    
                    self.issues.append(DriftIssue(
                        severity='CRITICAL',
                        drift_type='MISSING_COLUMN',
                        description=f"Model '{model.name}' has field '{field.name}' but column not found in table '{model.table_name}'",
                        model_name=model.name,
                        table_name=model.table_name,
                        field_name=field.name,
                        column_name=None,
                        suggestion=f"Add column '{field.name}' ({field.field_type}) to table '{model.table_name}' via migration",
                        model_location=f"{model.file_path}:{field.line_number}",
                        schema_location=self.schema[model.table_name][0].source_file if self.schema[model.table_name] else None
                    ))
    
    def _check_orphan_columns(self):
        """Find DB columns without corresponding model fields."""
        for table_name, columns in self.schema.items():
            model = self.model_map.get(table_name)
            if not model:
                continue
            
            model_field_names = {f.name.lower() for f in model.fields}
            
            # Add common excluded fields
            excluded = {'id', 'created_at', 'updated_at', 'deleted_at'}
            
            for col in columns:
                if col.name.lower() not in model_field_names and col.name.lower() not in excluded:
                    self.issues.append(DriftIssue(
                        severity='INFO',
                        drift_type='ORPHAN_COLUMN',
                        description=f"Table '{table_name}' has column '{col.name}' ({col.column_type}) but no matching field in model '{model.name}'",
                        model_name=model.name,
                        table_name=table_name,
                        field_name=None,
                        column_name=col.name,
                        suggestion=f"Add field '{col.name}' to model '{model.name}' or remove unused column",
                        model_location=f"{model.file_path}:{model.line_number}",
                        schema_location=col.source_file
                    ))
    
    def _check_type_mismatches(self):
        """Find type differences between model fields and DB columns."""
        for model in self.models:
            if model.table_name not in self.schema:
                continue
            
            db_columns = {c.name.lower(): c for c in self.schema[model.table_name]}
            
            for field in model.fields:
                col = db_columns.get(field.name.lower())
                if not col:
                    continue
                
                # Normalize types for comparison
                model_type = self._normalize_type(field.field_type)
                db_type = self._normalize_type(col.column_type)
                
                if model_type != db_type and model_type != 'UNKNOWN' and db_type != 'UNKNOWN':
                    # Some type differences are acceptable
                    compatible_pairs = {
                        ('VARCHAR', 'TEXT'), ('TEXT', 'VARCHAR'),
                        ('INTEGER', 'BIGINT'), ('BIGINT', 'INTEGER'),
                        ('TIMESTAMP', 'DATETIME'), ('DATETIME', 'TIMESTAMP'),
                        ('JSON', 'JSONB'), ('JSONB', 'JSON'),
                    }
                    
                    if (model_type, db_type) not in compatible_pairs:
                        self.issues.append(DriftIssue(
                            severity='WARNING',
                            drift_type='TYPE_MISMATCH',
                            description=f"Type mismatch for '{field.name}': model={model_type}, db={db_type}",
                            model_name=model.name,
                            table_name=model.table_name,
                            field_name=field.name,
                            column_name=col.name,
                            suggestion="Align types: consider ALTER COLUMN or model change",
                            model_location=f"{model.file_path}:{field.line_number}",
                            schema_location=col.source_file
                        ))
    
    def _check_nullable_mismatches(self):
        """Find nullable differences between model fields and DB columns."""
        for model in self.models:
            if model.table_name not in self.schema:
                continue
            
            db_columns = {c.name.lower(): c for c in self.schema[model.table_name]}
            
            for field in model.fields:
                col = db_columns.get(field.name.lower())
                if not col:
                    continue
                
                # If model says required but DB allows null (or vice versa)
                if field.nullable != col.nullable:
                    self.issues.append(DriftIssue(
                        severity='INFO',
                        drift_type='NULLABLE_MISMATCH',
                        description=f"Nullable mismatch for '{field.name}': model={'optional' if field.nullable else 'required'}, db={'nullable' if col.nullable else 'not null'}",
                        model_name=model.name,
                        table_name=model.table_name,
                        field_name=field.name,
                        column_name=col.name,
                        suggestion="Align nullable constraints via migration or model update",
                        model_location=f"{model.file_path}:{field.line_number}"
                    ))
    
    @staticmethod
    def _normalize_type(type_str: str) -> str:
        """Normalize type names for comparison."""
        mapping = {
            'STR': 'VARCHAR', 'STRING': 'VARCHAR',
            'INT': 'INTEGER', 'LONG': 'BIGINT',
            'BOOL': 'BOOLEAN', 'DICT': 'JSON',
            'LIST': 'ARRAY', 'DATETIME': 'TIMESTAMP',
        }
        return mapping.get(type_str.upper(), type_str.upper())


class ReportGenerator:
    """Generates reports in various formats."""
    
    def __init__(self, issues: list[DriftIssue], models: list[ORMModel],
                 schema: dict[str, list[ColumnDefinition]]):
        self.issues = issues
        self.models = models
        self.schema = schema
    
    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI DATABASE MODEL DRIFT CHECKER REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        critical = sum(1 for i in self.issues if i.severity == 'CRITICAL')
        warnings = sum(1 for i in self.issues if i.severity == 'WARNING')
        infos = sum(1 for i in self.issues if i.severity == 'INFO')
        
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  ORM Models Analyzed:       {len(self.models)}")
        lines.append(f"  Tables in Schema:          {len(self.schema)}")
        lines.append(f"  Critical Drift Issues:     {critical}")
        lines.append(f"  Warnings:                  {warnings}")
        lines.append(f"  Info Notes:                {infos}")
        lines.append("")
        
        # Group by type
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.drift_type].append(issue)
        
        # Detailed findings
        lines.append("DETAILED FINDINGS")
        lines.append("-" * 40)
        
        type_labels = {
            'MISSING_TABLE': '🔴 Missing Table (Model without DB table)',
            'MISSING_COLUMN': '🔴 Missing Column (Field without DB column)',
            'ORPHAN_COLUMN': '🟢 Orphan Column (DB column without field)',
            'TYPE_MISMATCH': '⚠️ Type Mismatch',
            'NULLABLE_MISMATCH': '💡 Nullable Mismatch'
        }
        
        for drift_type, issues in sorted(by_type.items()):
            label = type_labels.get(drift_type, drift_type)
            lines.append(f"\n{label} ({len(issues)} issues)")
            lines.append("  " + "-" * 36)
            
            for i, issue in enumerate(issues[:15], 1):
                lines.append(f"\n  {i}. [{issue.severity}]")
                lines.append(f"     {issue.description}")
                if issue.model_location:
                    lines.append(f"     Model:   {issue.model_location}")
                if issue.schema_location:
                    lines.append(f"     Schema:  {issue.schema_location}")
                lines.append(f"     💡 {issue.suggestion}")
            
            if len(issues) > 15:
                lines.append(f"\n  ... and {len(issues) - 15} more issues")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate machine-readable JSON report."""
        return {
            "summary": {
                "models_analyzed": len(self.models),
                "tables_in_schema": len(self.schema),
                "critical_count": sum(1 for i in self.issues if i.severity == 'CRITICAL'),
                "warning_count": sum(1 for i in self.issues if i.severity == 'WARNING'),
                "info_count": sum(1 for i in self.issues if i.severity == 'INFO'),
            },
            "drift_issues": [asdict(i) for i in self.issues],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Database Model Drift Checker - Detect model/schema mismatches',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python db_model_drift_checker.py
  python db_model_drift_checker.py --backend-dir ../backend --migrations-dir ../backend/database/migrations
  python db_model_drift_checker.py --output-format json > drift_report.json
"""
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory containing models (default: ../backend)')
    parser.add_argument('--migrations-dir', '-m', default='../backend/database/migrations',
                       help='Migrations directory (default: ../backend/database/migrations)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text', help='Output format')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit with error code if critical issues found')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    migrations_dir = (script_dir / args.migrations_dir).resolve()
    
    print("🗄️ SupremeAI Database Model Drift Checker")
    print(f"   Backend:      {backend_dir}")
    print(f"   Migrations:   {migrations_dir}")
    print()
    
    # Extract models and schema
    model_extractor = SQLAlchemyModelExtractor(backend_dir)
    models = model_extractor.extract_models()
    
    schema_extractor = MigrationSchemaExtractor(migrations_dir)
    schema = schema_extractor.extract_schema()
    
    # Check for drift
    checker = DriftChecker(models, schema)
    issues = checker.check()
    
    # Generate report
    generator = ReportGenerator(issues, models, schema)
    
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
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
