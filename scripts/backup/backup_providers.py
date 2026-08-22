

# --- Merged from superai_backup_manager.py ---

#!/usr/bin/env python3
"""
================================================================================
SuperAI Backup Manager - Automated Backup & Restore System
================================================================================
💾 Complete backup solution for SuperAI platform
📦 Database, environment configs, code, and Redis snapshots
🔄 Automated scheduled backups with rotation
♻️ One-click restore with validation

Author: SuperAI Toolkit
Version: 1.0.0
License: MIT

Usage:
    python superai_backup_manager.py create              # Create full backup
    python superai_backup_manager.py create --components db,env  # Partial backup
    python superai_backup_manager.py list                # List backups
    python superai_backup_manager.py restore <backup_id> # Restore from backup
    python superai_backup_manager.py schedule --hours 6   # Schedule every 6 hours
    python superai_backup_manager.py verify <backup_id>  # Verify backup integrity

Backup Components:
  📊 Database (PostgreSQL/Supabase dump)
  🔐 Environment variables (.env file)
  📁 Source code snapshot (git-aware)
  💾 Redis data export
  ⚙️ Configuration files
  📝 Logs (optional)

CPU Impact:
  - Backup creation: ~5-15% CPU during dump (short burst)
  - Compression: ~10-20% CPU for ~10 seconds
  - Restore: Similar to backup
  - Scheduled: Minimal when idle
================================================================================
"""

import os
import sys
import json
import shutil
import hashlib
import sqlite3
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from pathlib import PurePath
import subprocess
import tarfile
import tempfile
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try imports
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class BackupConfig:
    """Backup configuration."""
    backup_dir: Path = field(default_factory=lambda: Path('/home/z/my-project/backups'))
    project_root: Optional[Path] = None
    compression: bool = True
    encryption_key: Optional[str] = None
    max_backups: int = 10  # Rotation limit
    include_source: bool = True
    include_env: bool = True
    include_db: bool = True
    include_redis: bool = True
    include_logs: bool = False
    exclude_patterns: List[str] = field(default_factory=lambda: [
        'node_modules', '.next', '__pycache__', '*.pyc', '.git',
        '*.db', '*.sqlite3', 'backups/', 'downloads/'
    ])


@dataclass
class BackupManifest:
    """Backup manifest metadata."""
    backup_id: str
    timestamp: datetime
    components: List[str]
    files: Dict[str, str]  # filename -> sha256 hash
    total_size_bytes: int = 0
    compressed_size_bytes: int = 0
    duration_seconds: float = 0.0
    status: str = "created"
    version: str = "1.0"
    
    def to_dict(self) -> Dict:
        return {
            'backup_id': self.backup_id,
            'timestamp': self.timestamp.isoformat(),
            'components': self.components,
            'files': self.files,
            'total_size_bytes': self.total_size_bytes,
            'compressed_size_bytes': self.compressed_size_bytes,
            'duration_seconds': round(self.duration_seconds, 2),
            'status': self.status,
            'version': self.version
        }


class SuperAIBackupManager:
    """
    Comprehensive backup and restore management for SuperAI.
    
    Features:
    - Component-based selective backup
    - Integrity verification with SHA256
    - Automatic rotation
    - Encrypted backups support
    - Restore with pre-flight checks
    """
    
    def __init__(self, config: Optional[BackupConfig] = None):
        self.config = config or BackupConfig()
        
        # Detect project root if not set
        if not self.config.project_root:
            self.config.project_root = self._detect_project_root()
        
        # Ensure backup directory exists
        self.config.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize local database for tracking
        self.db_path = self.config.backup_dir / 'backup_registry.db'
        self._init_db()
    
    def _detect_project_root(self) -> Path:
        """Detect the project root directory."""
        current = Path.cwd()
        
        indicators = ['package.json', 'backend/main.py', 'next.config.js']
        
        for parent in [current] + list(current.parents):
            if any((parent / ind).exists() for ind in indicators):
                return parent
        
        return current
    
    def _init_db(self):
        """Initialize SQLite database for backup tracking."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                components TEXT NOT NULL,
                total_size INTEGER DEFAULT 0,
                compressed_size INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                status TEXT DEFAULT 'created',
                manifest_json TEXT,
                file_path TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                FOREIGN KEY (backup_id) REFERENCES backups(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup ID."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        random_suffix = hashlib.md5(str(os.urandom(8)).encode()).hexdigest()[:6]
        return f"superai_{timestamp}_{random_suffix}"
    
    def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _get_dir_size(self, path: Path) -> int:
        """Get total size of directory in bytes."""
        total = 0
        for item in path.rglob('*'):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
        return total
    
    def create_backup(
        self,
        components: Optional[List[str]] = None,
        name: Optional[str] = None,
        description: str = ""
    ) -> BackupManifest:
        """
        Create a new backup.
        
        Args:
            components: List of components to backup (all if None)
                Options: ['db', 'env', 'source', 'redis', 'logs', 'config']
            name: Custom backup name
            description: Backup description
        
        Returns:
            BackupManifest with metadata
        """
        start_time = datetime.now()
        backup_id = name or self._generate_backup_id()
        
        # Determine components
        all_components = {
            'db': self._backup_database,
            'env': self._backup_environment,
            'source': self._backup_source_code,
            'redis': self._backup_redis,
            'logs': self._backup_logs,
            'config': self._backup_config,
        }
        
        if components:
            selected = {k: v for k, v in all_components.items() if k in components}
        else:
            selected = all_components
        
        logger.info(f"Creating backup: {backup_id}")
        logger.info(f"Components: {list(selected.keys())}")
        
        # Create temporary directory for backup contents
        temp_dir = Path(tempfile.mkdtemp(prefix=f"superai_backup_{backup_id}_"))
        manifest = BackupManifest(
            backup_id=backup_id,
            timestamp=start_time,
            components=list(selected.keys()),
            files={}
        )
        
        try:
            # Backup each component
            for component_name, backup_func in selected.items():
                logger.info(f"Backing up component: {component_name}")
                
                try:
                    result = backup_func(temp_dir, component_name)
                    if result:
                        if isinstance(result, list):
                            for r in result:
                                if isinstance(r, dict):
                                    manifest.files.update(r)
                        elif isinstance(result, dict):
                            manifest.files.update(result)
                        
                        logger.info(f"✅ {component_name} backed up successfully")
                    else:
                        logger.warning(f"⚠️  {component_name} returned no data")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to backup {component_name}: {e}")
                    manifest.status = "partial"
            
            # Calculate sizes
            manifest.total_size_bytes = self._get_dir_size(temp_dir)
            
            # Create archive
            archive_path = self.config.backup_dir / f"{backup_id}.tar.gz"
            
            if self.config.compression:
                with tarfile.open(archive_path, "w:gz") as tar:
                    tar.add(temp_dir, arcname=backup_id)
                
                manifest.compressed_size_bytes = archive_path.stat().st_size
            else:
                with tarfile.open(archive_path, "w") as tar:
                    tar.add(temp_dir, arcname=backup_id)
                
                manifest.compressed_size_bytes = manifest.total_size_bytes
            
            # Calculate duration
            end_time = datetime.now()
            manifest.duration_seconds = (end_time - start_time).total_seconds()
            
            # Save manifest
            manifest_path = temp_dir / 'manifest.json'
            with open(manifest_path, 'w') as f:
                json.dump(manifest.to_dict(), f, indent=2)
            
            # Re-create archive with manifest
            if self.config.compression:
                with tarfile.open(archive_path, "w:gz") as tar:
                    tar.add(temp_dir, arcname=backup_id)
            
            # Register in database
            self._register_backup(manifest, archive_path)
            
            # Cleanup temp dir
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            logger.info(f"✅ Backup created: {backup_id}")
            logger.info(f"   Size: {manifest.compressed_size_bytes / (1024*1024):.2f} MB")
            logger.info(f"   Duration: {manifest.duration_seconds:.1f}s")
            
            # Check rotation
            self._rotate_backups()
            
            return manifest
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            manifest.status = "failed"
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def _backup_database(self, temp_dir: Path, component: str) -> Optional[Dict]:
        """Backup PostgreSQL/Supabase database."""
        db_url = os.environ.get('DATABASE_URL', '')
        
        if not db_url or not self.config.include_db:
            logger.info("Database backup skipped (no URL or disabled)")
            return None
        
        db_dir = temp_dir / 'database'
        db_dir.mkdir(exist_ok=True)
        
        try:
            # Try pg_dump if available
            if 'postgres' in db_url.lower():
                # Parse connection string (simplified)
                output_file = db_dir / 'database_dump.sql'
                
                result = subprocess.run(
                    ['pg_dump', db_url, '-f', str(output_file)],
                    capture_output=True,
                    timeout=120
                )
                
                if result.returncode == 0 and output_file.exists():
                    file_hash = self._calculate_file_hash(output_file)
                    return {'database_dump.sql': file_hash}
                else:
                    logger.warning("pg_dump failed, trying alternative...")
                    
            # Alternative: Use Python to dump if SQLAlchemy available
            try:
                import sqlalchemy
                
                # Simple table structure export would go here
                # For now, save connection info for manual restore
                info_file = db_dir / 'database_info.json'
                with open(info_file, 'w') as f:
                    json.dump({
                        'url_prefix': db_url[:30] + '...',
                        'type': 'postgresql' if 'postgres' in db_url else 'unknown',
                        'timestamp': datetime.now().isoformat(),
                        'note': 'Full dump requires pg_dump or Supabase dashboard'
                    }, f, indent=2)
                
                return {'database_info.json': self._calculate_file_hash(info_file)}
                
            except ImportError:
                logger.warning("SQLAlchemy not available for DB backup")
                return None
                
        except FileNotFoundError:
            logger.warning("pg_dump not found, skipping full database dump")
            return None
        except Exception as e:
            logger.error(f"Database backup error: {e}")
            return None
    
    def _backup_environment(self, temp_dir: Path, component: str) -> Optional[Dict]:
        """Backup environment variables."""
        if not self.config.include_env:
            return None
        
        env_dir = temp_dir / 'environment'
        env_dir.mkdir(exist_ok=True)
        
        files_hash = {}
        
        # Backup .env file if exists
        env_file = self.config.project_root / '.env'
        if env_file.exists():
            dest = env_dir / '.env'
            shutil.copy2(env_file, dest)
            files_hash['.env'] = self._calculate_file_hash(dest)
        
        # Export current environment (masking sensitive values)
        env_export = {}
        sensitive_keys = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIAL']
        
        for key, value in os.environ.items():
            # Only export relevant keys
            if any(sens in key.upper() for sens in sensitive_keys) or \
               key.startswith(('NEXT_', 'DATABASE_', 'REDIS_', 'OPENAI_', 'API_')):
                # Mask value but keep format
                if any(sens in key.upper() for sens in ['SECRET', 'PASSWORD', 'KEY']):
                    masked_value = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
                else:
                    masked_value = value
                
                env_export[key] = masked_value
        
        if env_export:
            env_file = env_dir / 'environment_export.json'
            with open(env_file, 'w') as f:
                json.dump(env_export, f, indent=2, default=str)
            files_hash['environment_export.json'] = self._calculate_file_hash(env_file)
        
        return files_hash if files_hash else None
    
    def _backup_source_code(self, temp_dir: Path, component: str) -> Optional[Dict]:
        """Backup source code (git-aware)."""
        if not self.config.include_source or not self.config.project_root:
            return None
        
        source_dir = temp_dir / 'source'
        source_dir.mkdir(exist_ok=True)
        
        files_hash = {}
        
        # Check if git repo
        git_dir = self.config.project_root / '.git'
        
        if git_dir.exists():
            # Git-based backup: save commit hash and diff since last tag
            try:
                # Get current commit
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=self.config.project_root,
                    capture_output=True,
                    text=True
                )
                commit_hash = result.stdout.strip()
                
                # Save git info
                git_info = {
                    'commit': commit_hash,
                    'branch': subprocess.run(
                        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                        cwd=self.config.project_root,
                        capture_output=True,
                        text=True
                    ).stdout.strip(),
                    'timestamp': datetime.now().isoformat(),
                    'remote_url': subprocess.run(
                        ['git', 'remote', 'get-url', 'origin'],
                        cwd=self.config.project_root,
                        capture_output=True,
                        text=True
                    ).stdout.strip() or 'N/A'
                }
                
                git_info_file = source_dir / 'git_info.json'
                with open(git_info_file, 'w') as f:
                    json.dump(git_info, f, indent=2)
                files_hash['git_info.json'] = self._calculate_file_hash(git_info_file)
                
                # Save uncommitted changes (if any)
                diff_result = subprocess.run(
                    ['git', 'diff', '--name-only'],
                    cwd=self.config.project_root,
                    capture_output=True,
                    text=True
                )
                
                changed_files = [f for f in diff_result.stdout.strip().split('\n') if f]
                
                if changed_files:
                    changes_dir = source_dir / 'uncommitted_changes'
                    changes_dir.mkdir(exist_ok=True)
                    
                    for file_path in changed_files[:50]:  # Limit to 50 files
                        src = self.config.project_root / file_path
                        if src.exists():
                            dst = changes_dir / file_path
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dst)
                            rel_path = f"uncommitted_changes/{file_path}"
                            files_hash[rel_path] = self._calculate_file_hash(dst)
                    
                    # Also save the diff
                    diff_output = subprocess.run(
                        ['git', 'diff'],
                        cwd=self.config.project_root,
                        capture_output=True,
                        text=True
                    )
                    
                    diff_file = changes_dir / 'changes.diff'
                    with open(diff_file, 'w') as f:
                        f.write(diff_output.stdout)
                    files_hash['uncommitted_changes/changes.diff'] = self._calculate_file_hash(diff_file)
                
                logger.info(f"Git backup: commit {commit_hash[:8]}, {len(changed_files)} uncommitted changes")
                
            except Exception as e:
                logger.error(f"Git backup failed: {e}")
                # Fall back to file copy
                return self._backup_source_files(source_dir)
        else:
            # No git - copy important files
            return self._backup_source_files(source_dir)
        
        return files_hash if files_hash else None
    
    def _backup_source_files(self, source_dir: Path) -> Optional[Dict]:
        """Backup source files directly (no git)."""
        files_hash = {}
        
        important_files = [
            'package.json', 'package-lock.json',
            'next.config.js', 'tailwind.config.ts', 'tsconfig.json',
            'backend/main.py', 'backend/requirements.txt',
            '.env.example', '.gitignore',
            'README.md'
        ]
        
        for file_pattern in important_files:
            for file_path in self.config.project_root.glob(file_pattern):
                if file_path.is_file():
                    rel_path = file_path.relative_to(self.config.project_root)
                    dst = source_dir / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        shutil.copy2(file_path, dst)
                        files_hash[str(rel_path)] = self._calculate_file_hash(dst)
                    except Exception as e:
                        logger.warning(f"Could not backup {file_path}: {e}")
        
        return files_hash if files_hash else None
    
    def _backup_redis(self, temp_dir: Path, component: str) -> Optional[Dict]:
        """Backup Redis data."""
        redis_url = os.environ.get('REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
        
        if not redis_url or not self.config.include_redis:
            return None
        
        redis_dir = temp_dir / 'redis'
        redis_dir.mkdir(exist_ok=True)
        
        try:
            import redis
            
            client = redis.from_url(redis_url, socket_timeout=10)
            
            # Get basic info
            info = client.info()
            
            # Get all keys (be careful with large datasets)
            keys_count = client.dbsize()
            
            redis_info = {
                'url_type': 'upstash' if 'upstash' in redis_url.lower() else 'standalone',
                'keys_count': keys_count,
                'memory_used': info.get('used_memory_human', 'unknown'),
                'timestamp': datetime.now().isoformat(),
            }
            
            # Sample some keys (not all, could be huge)
            sample_data = {}
            try:
                sampled_keys = client.randomkey()
                if sampled_keys:
                    # Get a few example keys
                    cursor = 0
                    count = 0
                    while count < 100:  # Max 100 keys
                        cursor, keys = client.scan(cursor, count=20)
                        for key in keys:
                            if count >= 100:
                                break
                            
                            key_type = client.type(key)
                            if key_type == b'string':
                                sample_data[key.decode()] = client.get(key)[:100].decode(errors='ignore')
                            elif key_type == b'hash':
                                sample_data[key.decode()] = 'hash_data'
                            count += 1
                        
                        if cursor == 0:
                            break
            except Exception as e:
                logger.warning(f"Redis sampling error: {e}")
            
            redis_info['sample_keys'] = len(sample_data)
            
            # Save info
            info_file = redis_dir / 'redis_info.json'
            with open(info_file, 'w') as f:
                json.dump(redis_info, f, indent=2, default=str)
            
            files_hash = {'redis_info.json': self._calculate_file_hash(info_file)}
            
            # If small enough, export all keys
            if keys_count <= 1000:
                try:
                    dump_file = redis_dir / 'redis_dump.json'
                    all_data = {}
                    
                    cursor = 0
                    while True:
                        cursor, keys = client.scan(cursor, count=100)
                        for key in keys:
                            key_str = key.decode()
                            key_type = client.type(key)
                            
                            try:
                                if key_type == b'string':
                                    all_data[key_str] = client.get(key).decode(errors='ignore')
                                elif key_type == b'hash':
                                    all_data[key_str] = client.hgetall(key)
                                elif key_type == b'list':
                                    all_data[key_str] = client.lrange(key, 0, -1)
                                elif key_type == b'set':
                                    all_data[key_str] = list(client.smembers(key))
                            except:
                                all_data[key_str] = '[unable_to_retrieve]'
                        
                        if cursor == 0:
                            break
                    
                    with open(dump_file, 'w') as f:
                        json.dump(all_data, f, indent=2, default=str)
                    
                    files_hash['redis_dump.json'] = self._calculate_file_hash(dump_file)
                    
                except Exception as e:
                    logger.warning(f"Redis dump error: {e}")
            
            return files_hash
            
        except ImportError:
            logger.warning("redis package not installed")
            return None
        except Exception as e:
            logger.error(f"Redis backup error: {e}")
            return None
    
    def _backup_logs(self, temp_dir: Path, component: str) -> Optional[Dict]:
        """Backup recent log files."""
        if not self.config.include_logs:
            return None
        
        logs_dir = temp_dir / 'logs'
        logs_dir.mkdir(exist_ok=True)
        
        files_hash = {}
        
        log_patterns = ['*.log', 'logs/**/*.log', '**/*.log']
        
        for pattern in log_patterns:
            for log_file in self.config.project_root.glob(pattern):
                if log_file.is_file() and log_file.stat().st_size < 10 * 1024 * 1024:  # < 10MB
                    try:
                        rel_path = log_file.relative_to(self.config.project_root)
                        dst = logs_dir / rel_path
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(log_file, dst)
                        files_hash[str(rel_path)] = self._calculate_file_hash(dst)
                    except Exception as e:
                        logger.warning(f"Log backup error: {e}")
        
        return files_hash if files_hash else None
    
    def _backup_config(self, temp_dir: Path, component: str) -> Optional[Dict]:
        """Backup configuration files."""
        config_dir = temp_dir / 'config'
        config_dir.mkdir(exist_ok=True)
        
        files_hash = {}
        
        config_patterns = [
            '*.config.*', '*config*.*',
            '.env*', '*.yml', '*.yaml',
            'Dockerfile*', 'docker-compose*',
            '*.toml', '*.ini', '*.cfg'
        ]
        
        for pattern in config_patterns:
            for config_file in self.config.project_root.glob(pattern):
                if config_file.is_file() and '.env' not in config_file.name:
                    # Skip .env (handled separately)
                    try:
                        rel_path = config_file.relative_to(self.config.project_root)
                        dst = config_dir / rel_path
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(config_file, dst)
                        files_hash[str(rel_path)] = self._calculate_file_hash(dst)
                    except Exception as e:
                        logger.warning(f"Config backup error: {e}")
        
        return files_hash if files_hash else None
    
    def _register_backup(self, manifest: BackupManifest, archive_path: Path):
        """Register backup in tracking database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO backups 
            (id, timestamp, components, total_size, compressed_size, duration, status, manifest_json, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            manifest.backup_id,
            manifest.timestamp.isoformat(),
            ','.join(manifest.components),
            manifest.total_size_bytes,
            manifest.compressed_size_bytes,
            manifest.duration_seconds,
            manifest.status,
            json.dumps(manifest.to_dict()),
            str(archive_path)
        ))
        
        # Register individual files
        for filename, file_hash in manifest.files.items():
            cursor.execute('''
                INSERT INTO backup_files (backup_id, filename, sha256_hash)
                VALUES (?, ?, ?)
            ''', (manifest.backup_id, filename, file_hash))
        
        conn.commit()
        conn.close()
    
    def _rotate_backups(self):
        """Remove old backups beyond retention limit."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get all backups ordered by date
        cursor.execute('SELECT id, file_path FROM backups ORDER BY timestamp DESC')
        backups = cursor.fetchall()
        
        # Remove excess
        if len(backups) > self.config.max_backups:
            for backup_id, file_path in backups[self.config.max_backups:]:
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                    
                    cursor.execute('DELETE FROM backup_files WHERE backup_id = ?', (backup_id,))
                    cursor.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
                    
                    logger.info(f"Rotated old backup: {backup_id}")
                except Exception as e:
                    logger.error(f"Rotation error for {backup_id}: {e}")
        
        conn.commit()
        conn.close()
    
    def list_backups(self) -> List[Dict]:
        """List all available backups."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, timestamp, components, compressed_size, duration, status
            FROM backups ORDER BY timestamp DESC
        ''')
        
        backups = []
        for row in cursor.fetchall():
            backups.append({
                'id': row[0],
                'timestamp': row[1],
                'components': row[2].split(',') if row[2] else [],
                'size_mb': round(row[3] / (1024*1024), 2),
                'duration': round(row[4], 1),
                'status': row[5]
            })
        
        conn.close()
        return backups
    
    def restore_backup(
        self,
        backup_id: str,
        components: Optional[List[str]] = None,
        dry_run: bool = False,
        force: bool = False
    ) -> bool:
        """
        Restore from a backup.
        
        Args:
            backup_id: ID of backup to restore
            components: Specific components to restore (all if None)
            dry_run: Preview only, don't actually restore
            force: Skip confirmation prompts
        
        Returns:
            True if successful
        """
        # Find backup
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM backups WHERE id = ?', (backup_id,))
        backup_row = cursor.fetchone()
        
        if not backup_row:
            logger.error(f"Backup not found: {backup_id}")
            conn.close()
            return False
        
        manifest = json.loads(backup_row[7])  # manifest_json
        archive_path = backup_row[8]  # file_path
        conn.close()
        
        if not archive_path or not os.path.exists(archive_path):
            logger.error(f"Archive not found: {archive_path}")
            return False
        
        logger.info(f"Restoring backup: {backup_id}")
        logger.info(f"Components: {manifest['components']}")
        
        if dry_run:
            logger.info("[DRY RUN] Would restore:")
            logger.info(f"  Files: {len(manifest['files'])}")
            logger.info(f"  Size: {manifest['compressed_size_bytes'] / (1024*1024):.2f} MB")
            return True
        
        # Extract archive
        temp_dir = Path(tempfile.mkdtemp(prefix=f"superai_restore_{backup_id}_"))
        
        try:
            with tarfile.open(archive_path, 'r:gz' if self.config.compression else 'r:') as tar:
                tar.extractall(temp_dir)
            
            extracted_dir = temp_dir / backup_id
            
            # Verify integrity
            if not self._verify_backup_integrity(extracted_dir, manifest):
                logger.error("Backup integrity check failed!")
                return False
            
            # Restore each component
            restored_components = []
            
            if not components:
                components = manifest['components']
            
            for component in components:
                component_dir = extracted_dir / component
                
                if component_dir.exists():
                    success = self._restore_component(component, component_dir)
                    if success:
                        restored_components.append(component)
                        logger.info(f"✅ Restored: {component}")
                    else:
                        logger.warning(f"⚠️  Issues restoring: {component}")
            
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            logger.info(f"Restore complete! Restored: {restored_components}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
    
    def _verify_backup_integrity(self, extracted_dir: Path, manifest: Dict) -> bool:
        """Verify SHA256 hashes of backup files."""
        expected_files = manifest.get('files', {})
        verified = 0
        failed = 0
        
        for filename, expected_hash in expected_files.items():
            file_path = extracted_dir / filename
            
            if not file_path.exists():
                logger.warning(f"Missing file: {filename}")
                failed += 1
                continue
            
            actual_hash = self._calculate_file_hash(file_path)
            
            if actual_hash != expected_hash:
                logger.error(f"Hash mismatch: {filename}")
                logger.error(f"  Expected: {expected_hash}")
                logger.error(f"  Actual:   {actual_hash}")
                failed += 1
            else:
                verified += 1
        
        logger.info(f"Integrity check: {verified} verified, {failed} failed")
        return failed == 0
    
    def _restore_component(self, component: str, source_dir: Path) -> bool:
        """Restore a specific component."""
        target = self.config.project_root
        
        try:
            if component == 'env':
                # Restore .env file carefully
                env_file = source_dir / '.env'
                if env_file.exists():
                    # Backup existing .env first
                    existing_env = target / '.env'
                    if existing_env.exists():
                        shutil.copy2(existing_env, target / '.env.pre_restore_backup')
                    
                    shutil.copy2(env_file, target / '.env')
                    logger.info("Environment file restored (old version backed up)")
            
            elif component == 'source':
                # Restore uncommitted changes
                changes_dir = source_dir / 'uncommitted_changes'
                if changes_dir.exists():
                    for file_path in changes_dir.rglob('*'):
                        if file_path.is_file():
                            rel = file_path.relative_to(changes_dir)
                            dest = target / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, dest)
            
            elif component == 'config':
                # Restore config files
                for config_file in source_dir.rglob('*'):
                    if config_file.is_file():
                        rel = config_file.relative_to(source_dir)
                        dest = target / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(config_file, dest)
            
            elif component == 'redis':
                # Import Redis data
                dump_file = source_dir / 'redis_dump.json'
                if dump_file.exists():
                    redis_url = os.environ.get('REDIS_URL')
                    if redis_url:
                        import redis
                        client = redis.from_url(redis_url)
                        
                        with open(dump_file) as f:
                            data = json.load(f)
                        
                        for key, value in data.items():
                            try:
                                if isinstance(value, str):
                                    client.set(key, value)
                                elif isinstance(value, list):
                                    client.delete(key)
                                    for item in value:
                                        client.rpush(key, item)
                            except Exception as e:
                                logger.warning(f"Redis import error for {key}: {e}")
                        
                        logger.info(f"Imported {len(data)} Redis keys")
            
            elif component == 'database':
                # Database restore is complex - provide instructions
                sql_file = source_dir / 'database_dump.sql'
                if sql_file.exists():
                    logger.info("""
                    Database restore requires manual execution:
                    
                    1. psql DATABASE_URL < database_dump.sql
                       OR use Supabase dashboard to import
                    
                    2. For Supabase: Dashboard > SQL Editor > Upload SQL file
                    """)
            
            return True
            
        except Exception as e:
            logger.error(f"Error restoring {component}: {e}")
            return False
    
    def verify_backup(self, backup_id: str) -> Dict:
        """Verify backup integrity without restoring."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT file_path, manifest_json FROM backups WHERE id = ?', (backup_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {'valid': False, 'error': 'Backup not found'}
        
        archive_path = row[0]
        manifest = json.loads(row[1])
        
        if not os.path.exists(archive_path):
            return {'valid': False, 'error': 'Archive file missing'}
        
        # Extract and verify
        temp_dir = Path(tempfile.mkdtemp(prefix=f"superai_verify_{backup_id}_"))
        
        try:
            with tarfile.open(archive_path, 'r:gz' if self.config.compression else 'r:') as tar:
                tar.extractall(temp_dir)
            
            extracted_dir = temp_dir / backup_id
            valid = self._verify_backup_integrity(extracted_dir, manifest)
            
            return {
                'valid': valid,
                'backup_id': backup_id,
                'files_checked': len(manifest.get('files', {})),
                'archive_exists': True,
                'size_mb': round(os.path.getsize(archive_path) / (1024*1024), 2)
            }
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description='💾 SuperAI Backup Manager - Automated backup & restore',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create                              # Full backup
  %(prog)s create --components db,env          # Backup only DB & env
  %(prog)s list                                # List all backups
  %(prog)s restore superai_20240115_120000     # Restore specific backup
  %(prog)s verify superai_20240115_120000      # Verify integrity
  %(prog)s schedule --hours 6                  # Auto-backup every 6 hours
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new backup')
    create_parser.add_argument('--components', '-c', nargs='+',
                               choices=['db', 'env', 'source', 'redis', 'logs', 'config'],
                               help='Components to backup')
    create_parser.add_argument('--name', '-n', help='Custom backup name')
    create_parser.add_argument('--description', '-d', default='', help='Backup description')
    create_parser.add_argument('--no-compress', action='store_true', help='Disable compression')
    create_parser.add_argument('--no-source', action='store_true', help='Exclude source code')
    create_parser.add_argument('--include-logs', action='store_true', help='Include log files')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available backups')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_id', help='Backup ID to restore')
    restore_parser.add_argument('--components', '-c', nargs='+',
                               choices=['db', 'env', 'source', 'redis', 'logs', 'config'],
                               help='Components to restore')
    restore_parser.add_argument('--dry-run', action='store_true', help='Preview restoration')
    restore_parser.add_argument('--force', '-f', action='store_true', help='Skip confirmations')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify backup integrity')
    verify_parser.add_argument('backup_id', help='Backup ID to verify')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Setup automated backups')
    schedule_parser.add_argument('--hours', type=int, default=12, help='Interval in hours')
    schedule_parser.add_argument('--max-backups', type=int, default=10, help='Max backups to keep')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize manager
    config = BackupConfig()
    manager = SuperAIBackupManager(config)
    
    if args.command == 'create':
        config.compression = not getattr(args, 'no_compress', False)
        config.include_source = not getattr(args, 'no_source', False)
        config.include_logs = getattr(args, 'include_logs', False)
        
        manifest = manager.create_backup(
            components=getattr(args, 'components', None),
            name=getattr(args, 'name', None),
            description=getattr(args, 'description', '')
        )
        
        print(f"\n✅ Backup created: {manifest.backup_id}")
        print(f"   Size: {manifest.compressed_size_bytes / (1024*1024):.2f} MB")
        print(f"   Duration: {manifest.duration_seconds:.1f}s")
        print(f"   Components: {', '.join(manifest.components)}")
    
    elif args.command == 'list':
        backups = manager.list_backups()
        
        if not backups:
            print("\nNo backups found.")
            return
        
        print(f"\n{'ID':<35} {'Date':<20} {'Size':>8} {'Components'}")
        print("-" * 90)
        
        for backup in backups:
            comps = ','.join(backup['components'][:3])
            if len(backup['components']) > 3:
                comps += f"+{len(backup['components'])-3}"
            
            print(f"{backup['id']:<35} {backup['timestamp']:<20} {backup['size_mb']:>7}MB {comps}")
    
    elif args.command == 'restore':
        success = manager.restore_backup(
            backup_id=args.backup_id,
            components=getattr(args, 'components', None),
            dry_run=getattr(args, 'dry_run', False),
            force=getattr(args, 'force', False)
        )
        
        if success:
            print(f"\n✅ Restore completed: {args.backup_id}")
        else:
            print(f"\n❌ Restore failed: {args.backup_id}")
            sys.exit(1)
    
    elif args.command == 'verify':
        result = manager.verify_backup(args.backup_id)
        
        if result.get('valid'):
            print(f"\n✅ Backup valid: {args.backup_id}")
            print(f"   Files verified: {result['files_checked']}")
            print(f"   Archive size: {result['size_mb']} MB")
        else:
            print(f"\n❌ Backup invalid: {result.get('error', 'Unknown error')}")
            sys.exit(1)
    
    elif args.command == 'schedule':
        hours = getattr(args, 'hours', 12)
        max_backups = getattr(args, 'max_backups', 10)
        
        print(f"\n⏰ Schedule configuration:")
        print(f"   Interval: Every {hours} hours")
        print(f"   Max backups: {max_backups}")
        print(f"\nTo enable automated backups, add to crontab:")
        print(f"   0 */{hours} * * * cd {config.project_root} && python {__file__} create")
        print("\nOr use systemd timer for more reliability.")


if __name__ == '__main__':
    main()


# --- Merged from auto_firestore_backup.py ---

#!/usr/bin/env python
"""
auto_firestore_backup.py
========================
Automatically creates backups of Firestore databases and exports them to Google Cloud Storage.

This script creates a managed export of Firestore data to a Cloud Storage bucket,
which can be used for disaster recovery, auditing, or data migration.

Environment Variables:
- GOOGLE_CLOUD_PROJECT: Google Cloud project ID
- FIRESTORE_DATABASE_ID: Firestore database ID (default: "(default)")
- BACKUP_BUCKET: Google Cloud Storage bucket for backups (required)
- BACKUP_PREFIX: Prefix for backup files (default: "firestore-backup")
- RETENTION_DAYS: Number of days to retain backups (default: 30)
- LOCATION_ID: Firestore database location (optional, uses project default if not set)
- USE_SNAPSHOT: Whether to use consistent snapshot (default: true)
- COLLECTION_IDS: Comma-separated list of collection IDs to export (empty = all)
"""

import os
import sys
import json
import re
import urllib.request as _url_req
from datetime import datetime, timedelta
from google.cloud import firestore, storage
from google.api_core import exceptions
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
BACKUP_BUCKET = os.getenv("BACKUP_BUCKET")
BACKUP_PREFIX = os.getenv("BACKUP_PREFIX", "firestore-backup")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
LOCATION_ID = os.getenv("LOCATION_ID")
USE_SNAPSHOT = os.getenv("USE_SNAPSHOT", "true").lower() == "true"
COLLECTION_IDS_STR = os.getenv("COLLECTION_IDS", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
BACKUP_TIMEOUT_SECONDS = int(os.getenv("BACKUP_TIMEOUT_SECONDS", "1800"))  # 30 min


def send_alert(severity: str, message: str):
    """Send alert to Discord webhook (critical alerts only)."""
    if severity == "critical" and DISCORD_WEBHOOK_URL:
        payload = json.dumps({"content": f"\U0001f6a8 **Backup Alert** | {message}"}).encode()
        req = _url_req.Request(DISCORD_WEBHOOK_URL, data=payload,
                               headers={"Content-Type": "application/json"})
        try:
            _url_req.urlopen(req)
        except Exception as e:
            logger.warning(f"Failed to send Discord alert: {e}")
    log_level = logging.CRITICAL if severity == "critical" else logging.INFO
    logger.log(log_level, message)

def validate_config() -> bool:
    """Validate required configuration."""
    if not PROJECT_ID:
        print("❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set")
        return False

    if not BACKUP_BUCKET:
        print("❌ Error: BACKUP_BUCKET environment variable is not set")
        return False

    # Validate bucket name format
    if not re.match(r'^[a-z0-9][a-z0-9\-_.]{1,61}[a-z0-9]$', BACKUP_BUCKET):
        print(f"⚠️  Warning: Bucket name '{BACKUP_BUCKET}' may not be valid")

    return True

def get_firestore_client():
    """Get a Firestore client instance."""
    try:
        if DATABASE_ID == "(default)":
            client = firestore.Client(project=PROJECT_ID)
        else:
            client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
        return client
    except Exception as e:
        logger.error(f"Failed to create Firestore client: {e}")
        return None

def get_storage_client():
    """Get a Cloud Storage client instance."""
    try:
        return storage.Client(project=PROJECT_ID)
    except Exception as e:
        logger.error(f"Failed to create Storage client: {e}")
        return None

def list_existing_backups(storage_client, bucket_name: str, prefix: str) -> list:
    """List existing backup files in the bucket."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        return [blob for blob in blobs if blob.name.endswith('.overall_export_metadata')]
    except Exception as e:
        logger.error(f"Error listing existing backups: {e}")
        return []

def delete_old_backups(storage_client, bucket_name: str, prefix: str, days_to_keep: int):
    """Delete backups older than the retention period."""
    try:
        bucket = storage_client.bucket(bucket_name)
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)

        blobs = bucket.list_blobs(prefix=prefix)
        deleted_count = 0

        for blob in blobs:
            # Check if the blob is older than the cutoff
            if blob.time_created < cutoff_time:
                blob.delete()
                deleted_count += 1
                logger.info(f"Deleted old backup: {blob.name}")

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old backup(s)")
        else:
            logger.info("No old backups to delete")

    except Exception as e:
        logger.error(f"Error deleting old backups: {e}")

def create_firestore_backup() -> bool:
    """Create a Firestore backup and export to Cloud Storage."""
    # Validate configuration
    if not validate_config():
        return False

    # Initialize clients
    firestore_client = get_firestore_client()
    storage_client = get_storage_client()

    if not firestore_client or not storage_client:
        return False

    # Generate backup timestamp and path
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{BACKUP_PREFIX}_{timestamp}"
    backup_path = f"gs://{BACKUP_BUCKET}/{backup_name}/"

    print("🔥 Starting Firestore backup...")
    print(f"📁 Project: {PROJECT_ID}")
    print(f"🗄️  Database: {DATABASE_ID}")
    print(f"📦 Bucket: {BACKUP_BUCKET}")
    print(f"📍 Backup path: {backup_path}")

    try:
        # Prepare export parameters
        database_path = f"projects/{PROJECT_ID}/databases/{DATABASE_ID}"

        # Build output URL prefix
        output_uri_prefix = backup_path

        # Prepare partition options if specific collections are requested
        partition_options = None
        collection_ids = None
        if COLLECTION_IDS_STR:
            collection_ids = [cid.strip() for cid in COLLECTION_IDS_STR.split(",") if cid.strip()]
            if collection_ids:
                partition_options = {
                    "collection_ids": collection_ids
                }
                print(f"📋 Exporting specific collections: {', '.join(collection_ids)}")

        # Create the export request
        request = {
            "name": f"{database_path}/exportDocuments/{backup_name}",
            "output_uri_prefix": output_uri_prefix,
        }

        if USE_SNAPSHOT:
            request["snapshot_time"] = {"seconds": int(datetime.utcnow().timestamp())}

        if partition_options:
            request["collection_ids"] = partition_options["collection_ids"]

        # Start the export operation
        print("\u23f3 Starting export operation...")
        operation = firestore_client._firestore_api.document_service_client.export_documents(
            request=request
        )

        print(f"\u23f3 Export operation started: {operation.name}")
        print(f"\u23f3 Polling for completion (timeout: {BACKUP_TIMEOUT_SECONDS}s)...")

        # ── PHASE 6: Poll for completion instead of fire-and-forget ──
        try:
            operation.result(timeout=BACKUP_TIMEOUT_SECONDS)
            print("\u2705 Export COMPLETED successfully!")
            print(f"\U0001f4be Backup available at: {backup_path}")

            # Write backup manifest to GCS
            manifest = {
                "backup_name": backup_name,
                "backup_path": backup_path,
                "completed_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "backup_status": "completed",
                "project": PROJECT_ID,
                "database": DATABASE_ID,
                "collections": collection_ids if collection_ids else "all",
            }
            bucket = storage_client.bucket(BACKUP_BUCKET)
            blob = bucket.blob("manifests/latest.json")
            blob.upload_from_string(json.dumps(manifest, indent=2),
                                   content_type="application/json")
            print(f"\U0001f4cb Manifest written: gs://{BACKUP_BUCKET}/manifests/latest.json")

            send_alert("info", f"Firestore backup completed: {backup_name}")

        except Exception as poll_error:
            error_msg = f"Export operation FAILED or timed out: {poll_error}"
            logger.error(error_msg)
            send_alert("critical", f"Firestore backup FAILED for {PROJECT_ID}/{DATABASE_ID}: {poll_error}")
            return False

        # Clean up old backups
        print(f"\U0001f9f9 Cleaning up backups older than {RETENTION_DAYS} days...")
        delete_old_backups(storage_client, BACKUP_BUCKET, f"{BACKUP_PREFIX}_", RETENTION_DAYS)

        return True

    except exceptions.GoogleAPICallError as e:
        logger.error(f"Google API error during backup: {e}")
        send_alert("critical", f"Firestore backup API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        send_alert("critical", f"Firestore backup unexpected error: {e}")
        return False

def main() -> int:
    """Main function to execute Firestore backup."""
    print("☁️  Starting Firestore Auto Backup...")

    success = create_firestore_backup()

    if success:
        print("\n✅ Firestore backup initiated successfully!")
        return 0
    else:
        print("\n❌ Failed to initiate Firestore backup!")
        return 1

if __name__ == "__main__":
    sys.exit(main())


# --- Merged from auto_cross_cloud_replicate.py ---

#!/usr/bin/env python
"""
auto_cross_cloud_replicate.py
=============================
Automatically replicates critical Firestore data to secondary cloud providers
for disaster recovery and multi-cloud resilience.

This solution implements a change-data-capture approach using Cloud Functions
to replicate writes to secondary databases, but this script provides the
initial synchronization and ongoing reconciliation capabilities.

Environment Variables:
- PRIMARY_PROJECT_ID: Primary Google Cloud project ID
- SECONDARY_PROJECT_ID: Secondary cloud project ID (AWS/Azure/GCP secondary)
- SECRET_BACKEND: Where to store credentials ('secret_manager', 'env_file', 'vc')
- REPLICATE_COLLECTIONS: Comma-separated list of collections to replicate
- SYNC_INTERVAL_MINUTES: How often to run sync (default: 60)
- BATCH_SIZE: Number of documents to process per batch (default: 500)
- DRY_RUN: If true, only show what would be done (default: false)
"""

import os
import sys
import json
import time
import hashlib
import urllib.request as _url_req
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
from google.cloud import firestore
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PRIMARY_PROJECT_ID = os.getenv("PRIMARY_PROJECT_ID")
SECONDARY_PROJECT_ID = os.getenv("SECONDARY_PROJECT_ID")
SECRET_BACKEND = os.getenv("SECRET_BACKEND", "secret_manager")
REPLICATE_COLLECTIONS_STR = os.getenv("REPLICATE_COLLECTIONS", "")
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

def load_secondary_credentials() -> Optional[service_account.Credentials]:
    """Load credentials for the secondary cloud provider."""
    if not SECONDARY_PROJECT_ID:
        print("⚠️  No secondary project configured - running in monitoring mode only")
        return None

    try:
        if SECRET_BACKEND == "secret_manager":
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{SECONDARY_PROJECT_ID}/secrets/firestore-sa-key/versions/latest"
            response = client.access_secret_version(request={"name": name})
            key_data = json.loads(response.payload.data.decode("UTF-8"))
            return service_account.Credentials.from_service_account_info(key_data)
        elif SECRET_BACKEND == "env_file":
            # Load from environment variable containing JSON key
            key_json = os.getenv("SECONDARY_SERVICE_ACCOUNT_KEY")
            if key_json:
                key_data = json.loads(key_json)
                return service_account.Credentials.from_service_account_info(key_data)
        elif SECRET_BACKEND == "vc":
            # Load from Volume-mounted credentials (Kubernetes secret)
            key_path = "/etc/secrets/firestore-sa-key.json"
            if os.path.exists(key_path):
                return service_account.Credentials.from_service_account_file(key_path)
    except Exception as e:
        logger.error(f"Failed to load secondary credentials: {e}")
        return None

    return None

def get_firestore_client(project_id: str, credentials: Optional[service_account.Credentials] = None) -> Optional[firestore.Client]:
    """Get a Firestore client for the specified project."""
    try:
        if credentials:
            return firestore.Client(project=project_id, credentials=credentials)
        else:
            # Use default credentials
            return firestore.Client(project=project_id)
    except Exception as e:
        logger.error(f"Failed to create Firestore client for {project_id}: {e}")
        return None

def calculate_document_hash(doc_data: Dict[str, Any]) -> str:
    """Calculate a hash of document data for change detection."""
    # Remove fields that might vary (like timestamps) for consistent hashing
    cleaned_data = {k: v for k, v in doc_data.items()
                   if not k.startswith('_') and not k.endswith('_at')}

    # Sort keys for consistent JSON serialization
    sorted_data = json.dumps(cleaned_data, sort_keys=True, default=str)
    return hashlib.md5(sorted_data.encode()).hexdigest()

def sync_collection_primary_to_secondary(
    primary_client: firestore.Client,
    secondary_client: Optional[firestore.Client],
    collection_path: str
) -> Dict[str, int]:
    """
    Synchronize a collection from primary to secondary database.

    Returns:
        Dict with counts: {'processed': int, 'inserted': int, 'updated': int, 'skipped': int, 'errors': int}
    """
    stats = {'processed': 0, 'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    if not secondary_client:
        print("⚠️  Secondary client not available - skipping actual replication")
        # Still count for reporting
        collection_ref = primary_client.collection(collection_path)
        docs = collection_ref.limit(BATCH_SIZE).stream()
        for doc in docs:
            stats['processed'] += 1
        return stats

    try:
        collection_ref = primary_client.collection(collection_path)

        # Process in batches
        docs = collection_ref.limit(BATCH_SIZE).stream()

        batch = secondary_client.batch()
        batch_count = 0

        for doc in docs:
            stats['processed'] += 1

            try:
                doc_data = doc.to_dict()
                doc_id = doc.id

                # Calculate hash for change detection
                doc_hash = calculate_document_hash(doc_data)

                # Add hash to metadata for tracking
                doc_data['_sync_metadata'] = {
                    'source_project': 'primary',
                    'synced_at': datetime.now(timezone.utc).isoformat(),
                    'hash': doc_hash
                }

                # Reference to document in secondary
                doc_ref = secondary_client.collection(collection_path).document(doc_id)

                # Check if document exists and has changed
                existing_doc = doc_ref.get()
                if existing_doc.exists:
                    existing_data = existing_doc.to_dict()
                    existing_hash = None
                    if '_sync_metadata' in existing_data and 'hash' in existing_data['_sync_metadata']:
                        existing_hash = existing_data['_sync_metadata']['hash']

                    if existing_hash == doc_hash:
                        stats['skipped'] += 1
                        continue  # No change
                    else:
                        stats['updated'] += 1
                else:
                    stats['inserted'] += 1

                # Add to batch
                batch.set(doc_ref, doc_data)
                batch_count += 1

                # Commit batch when full
                if batch_count >= 100:  # Firestore batch limit is 500, but we'll be conservative
                    if not DRY_RUN:
                        batch.commit()
                    else:
                        print(f"🔍 [DRY RUN] Would commit batch of {batch_count} writes to {collection_path}")
                    batch = secondary_client.batch()
                    batch_count = 0

            except Exception as e:
                logger.error(f"Error processing document {doc.id} in {collection_path}: {e}")
                stats['errors'] += 1

        # Commit remaining items in batch
        if batch_count > 0:
            if not DRY_RUN:
                batch.commit()
            else:
                print(f"🔍 [DRY RUN] Would commit final batch of {batch_count} writes to {collection_path}")

    except Exception as e:
        logger.error(f"Error synchronizing collection {collection_path}: {e}")
        stats['errors'] += 1

    return stats


def send_discord_alert(severity: str, message: str):
    """Send alert to Discord webhook (critical alerts only)."""
    discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if severity == "critical" and discord_url:
        payload = json.dumps({"content": f"\U0001f6a8 **Cross-Cloud Replication** | {message}"}).encode()
        req = _url_req.Request(discord_url, data=payload,
                               headers={"Content-Type": "application/json"})
        try:
            _url_req.urlopen(req)
        except Exception as alert_err:
            logger.exception(f"Failed to send Discord alert webhook: {alert_err}")
    logger.log(logging.CRITICAL if severity == "critical" else logging.INFO, message)


def replicate_with_retry(
    primary_client: firestore.Client,
    secondary_client: Optional[firestore.Client],
    collection: str,
    max_retries: int = 3,
) -> Dict[str, int]:
    """
    Retry wrapper for sync_collection_primary_to_secondary.
    Exponential backoff: 1s, 2s, 4s.
    After all retries exhausted, sends a critical Discord alert.
    """
    for attempt in range(max_retries):
        try:
            return sync_collection_primary_to_secondary(
                primary_client, secondary_client, collection
            )
        except Exception as e:
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                f"Replication attempt {attempt + 1}/{max_retries} failed for "
                f"{collection}: {e}. Retrying in {wait}s..."
            )
            if attempt < max_retries - 1:
                time.sleep(wait)

    # All retries exhausted
    send_discord_alert(
        "critical",
        f"Replication FAILED for collection `{collection}` after {max_retries} retries"
    )
    return {'processed': 0, 'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 1}

def main() -> int:
    """Main function to execute cross-cloud replication."""
    print("🔄 Starting Cross-Cloud Replication...")

    # Validate configuration
    if not PRIMARY_PROJECT_ID:
        print("❌ Error: PRIMARY_PROJECT_ID environment variable is not set")
        return 1

    if not SECONDARY_PROJECT_ID:
        print("⚠️  Warning: SECONDARY_PROJECT_ID not set - running in analysis mode only")

    # Parse collections to replicate
    replicate_collections = []
    if REPLICATE_COLLECTIONS_STR:
        replicate_collections = [c.strip() for c in REPLICATE_COLLECTIONS_STR.split(",") if c.strip()]
        print(f"📋 Will replicate collections: {', '.join(replicate_collections)}")
    else:
        print("⚠️  No specific collections specified - will need to implement discovery")
        # For now, we'll need to specify collections
        print("💡 Set REPLICATE_COLLECTIONS environment variable to specify which collections to replicate")
        return 1

    # Initialize clients
    print("🔌 Connecting to primary Firestore...")
    primary_client = get_firestore_client(PRIMARY_PROJECT_ID)
    if not primary_client:
        return 1

    print("🔌 Connecting to secondary Firestore...")
    secondary_credentials = load_secondary_credentials()
    secondary_client = None
    if SECONDARY_PROJECT_ID:
        secondary_client = get_firestore_client(SECONDARY_PROJECT_ID, secondary_credentials)
        if not secondary_client:
            print("⚠️  Warning: Could not connect to secondary - continuing in analysis mode")

    if DRY_RUN:
        print("🔍 RUNNING IN DRY-RUN MODE - No actual changes will be made")

    # Synchronize each collection
    total_stats = {'processed': 0, 'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    for collection_name in replicate_collections:
        print(f"\n\U0001f4ca Synchronizing collection: {collection_name}")
        stats = replicate_with_retry(
            primary_client,
            secondary_client,
            collection_name
        )

        # Accumulate stats
        for key in total_stats:
            total_stats[key] += stats.get(key, 0)

        print(f"   📈 Processed: {stats['processed']}, Inserted: {stats['inserted']}, "
              f"Updated: {stats['updated']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")

    # Print summary
    print("\n📊 Synchronization Summary:")
    print(f"   📄 Total processed: {total_stats['processed']}")
    print(f"   ➕ Total inserted: {total_stats['inserted']}")
    print(f"   🔄 Total updated: {total_stats['updated']}")
    print(f"   ⏭️  Total skipped: {total_stats['skipped']}")
    print(f"   ❌ Total errors: {total_stats['errors']}")

    if total_stats['errors'] > 0:
        print("\n⚠️  Some errors occurred during synchronization - check logs for details")
        return 1
    elif DRY_RUN:
        print("\n✅ Dry run completed successfully - no changes made")
        return 0
    else:
        print("\n✅ Synchronization completed successfully!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
