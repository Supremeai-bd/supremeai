"""
Disaster Recovery Agent for SupremeAI 2.0
Handles automated backup and recovery procedures to ensure system resilience.
"""

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.cache.redis_manager import redis_manager
from core.config import settings
from core.llm.token_deductor import TokenDeductor
from core.logging_config import logger
from core.utils.background_tasks import track_task

# বাংলা মন্তব্য (#3164): durable destination স্কিম — শুধু এই prefix দিয়ে
# শুরু হলে backup অফ-কন্টেইনার ধরা হয়; বাকি সব (local path) ephemeral।
DURABLE_SCHEMES = ("supabase-storage://", "s3://")

# বাংলা: ephemeral staging dir — আর্কাইভ শুধু সাময়িকভাবে এখানে থাকে,
# durable upload সফল হলেই মুছে ফেলা হয় (free-tier disk guard)।
DR_STAGING_DIR = os.getenv("DR_STAGING_DIR", "/tmp/dr-staging")


@dataclass
class BackupResult:
    """Data class to hold backup operation results."""

    backup_id: str
    timestamp: datetime
    size_bytes: int
    location: str
    status: str  # success, failed, partial
    verification_hash: str
    components_backed_up: list[str]
    duration_seconds: float


@dataclass
class RecoveryResult:
    """Data class to hold recovery operation results."""

    recovery_id: str
    timestamp: datetime
    backup_id: str
    status: str  # success, failed, partial
    recovered_components: list[str]
    duration_seconds: float
    notes: str


class DisasterRecoveryAgent:
    """Agent that handles automated backup and recovery procedures."""

    def __init__(self):
        self.name = "Disaster Recovery Agent"
        self.token_deductor = TokenDeductor()
        self.backup_history_key = "disaster_recovery:backup_history"
        self.recovery_history_key = "disaster_recovery:recovery_history"
        self.recovery_plan_key = "disaster_recovery:recovery_plans"
        self.system_state_key = "disaster_recovery:system_state"
        # বাংলা (#3164): durable destination parse — একবারই, __init__-এ।
        self.durable_destination = self._parse_durable_destination()

        # Define critical system components that need backup.
        # বাংলা: প্রতিটা component-এর paths env var দিয়ে override করা যায় (comma-separated)।
        # env var না থাকলে sensible defaults ব্যবহার হয়। এটি "zero-hardcoded" principle follow করে।
        self.critical_components = {
            "database": {
                "paths": self._env_paths(
                    "DR_DB_PATHS", [getattr(settings, "DATABASE_URL", ""), "/data/db.sqlite3"]
                ),
                "backup_method": "sql_dump",
                "restore_method": "sql_restore",
                "priority": "high",
            },
            "configuration": {
                "paths": self._env_paths("DR_CONFIG_PATHS", ["/config/", "./config/", "/etc/app/"]),
                "backup_method": "file_copy",
                "restore_method": "file_copy",
                "priority": "high",
            },
            "user_data": {
                "paths": self._env_paths(
                    "DR_USER_DATA_PATHS", ["/data/users/", "/storage/uploads/"]
                ),
                "backup_method": "archive",
                "restore_method": "extract",
                "priority": "high",
            },
            "skills": {
                "paths": self._env_paths("DR_SKILLS_PATHS", ["/skills/", "/backend/skills/"]),
                "backup_method": "archive",
                "restore_method": "extract",
                "priority": "medium",
            },
            "models": {
                "paths": self._env_paths("DR_MODELS_PATHS", ["/models/", "/backend/models/"]),
                "backup_method": "archive",
                "restore_method": "extract",
                "priority": "medium",
            },
            "logs": {
                "paths": self._env_paths("DR_LOGS_PATHS", ["/logs/", "/var/log/app/"]),
                "backup_method": "archive",
                "restore_method": "skip",
                "priority": "low",
            },
        }

        # Recovery priorities (order of restoration)
        self.recovery_priority_order = [
            "configuration",
            "database",
            "user_data",
            "skills",
            "models",
            "logs",
        ]

        # Initialize default recovery plans
        self.default_recovery_plans = {
            "minimal_service_restoration": {
                "name": "Minimal Service Restoration",
                "description": "Restore only essential services to resume basic operations",
                "components": ["configuration", "database"],
                "target_recovery_time": 300,  # 5 minutes
                "target_point_objective": 3600,  # 1 hour
            },
            "full_restoration": {
                "name": "Full System Restoration",
                "description": "Complete system restoration with all data and functionality",
                "components": list(self.critical_components.keys()),
                "target_recovery_time": 3600,  # 1 hour
                "target_point_objective": 900,  # 15 minutes
            },
            "user_data_restoration": {
                "name": "User Data Restoration",
                "description": "Restore only user data while keeping system operational",
                "components": ["user_data"],
                "target_recovery_time": 1800,  # 30 minutes
                "target_point_objective": 1800,  # 30 minutes
            },
        }

    # ------------------------------------------------------------------
    # #3164 Durability layer — off-container destination, checksum,
    # encryption, runtime guard (ephemeral-disk enablement ব্লক)
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_durable_destination() -> dict[str, str] | None:
        """DR_BACKUP_DESTINATION পার্স করে durable হলে dict, নইলে None।

        # বাংলা: বৈধ ফরম্যাট —
        #   supabase-storage://<bucket>/<prefix>
        #   s3://<bucket>/<prefix>
        # অন্য যেকোনো মান (local path, /backups, /tmp...) = ephemeral → guard ব্লক
        """
        dest = os.getenv("DR_BACKUP_DESTINATION", "").strip()
        if not dest:
            return None
        for scheme in DURABLE_SCHEMES:
            if dest.startswith(scheme):
                rest = dest[len(scheme):]
                bucket, _, prefix = rest.partition("/")
                if not bucket:
                    return None
                return {"scheme": scheme.rstrip(":/"), "bucket": bucket,
                        "prefix": prefix.strip("/")}
        return None

    def is_backup_destination_durable(self) -> bool:
        """Runtime guard — ব্যাকআপ গন্তব্য অফ-কন্টেইনার durable কি না।

        # বাংলা (#3164 verification): ephemeral local storage-এ DR agent
        # enable করা যাবে না — এটাই এই guard-এর একমাত্র কাজ।
        """
        return self.durable_destination is not None

    def _encryption_key(self) -> bytes | None:
        """DR_BACKUP_ENCRYPTION_KEY (Fernet key) — optional at-rest encryption।"""
        key = os.getenv("DR_BACKUP_ENCRYPTION_KEY", "").strip()
        if not key:
            return None
        from cryptography.fernet import Fernet  # local import — optional dep path
        return key.encode()

    async def _upload_to_durable(self, local_path: str, backup_id: str) -> str:
        """Staged আর্কাইভ durable destination-এ আপলোড + checksum verify।

        # বাংলা: আপলোডের পর **download-back verify** — ফিরে পাওয়া byte-এর
        # sha256 স্থানীয় আর্কাইভের সাথে মিললেই success (integrity end-to-end)।
        # সফল হলে local staged কপি মুছে ফেলা হয় (free-tier disk)।
        """
        dest = self.durable_destination
        if not dest:
            raise ValueError("durable destination not configured")

        from database.storage_client import StorageClient

        provider = "supabase" if dest["scheme"] == "supabase-storage" else "s3"
        client = StorageClient(provider=provider)
        client.bucket_name = dest["bucket"]
        remote_path = "/".join(p for p in (dest["prefix"], f"{backup_id}.zip") if p)

        # বাংলা: optional at-rest encryption — key থাকলে আপলোডের আগে Fernet এনক্রিপ্ট
        upload_path = local_path
        key = self._encryption_key()
        if key:
            from cryptography.fernet import Fernet
            cipher = Fernet(key)
            encrypted_path = local_path + ".enc"
            with open(local_path, "rb") as src:
                token = cipher.encrypt(src.read())
            with open(encrypted_path, "wb") as out:
                out.write(token)
            upload_path = encrypted_path

        result = client.upload_file(upload_path, remote_path)
        if result.get("status") != "success":
            raise RuntimeError(f"durable upload failed: {result.get('error', 'unknown')}")

        # download-back checksum verification (integrity proof)
        # বাংলা: তুলনা করা হয় **upload_path** (এনক্রিপ্টেড হলে এনক্রিপ্টেড byte) —
        # plaintext hash আলাদাভাবে history-তে যায় (restore-এ decrypt-এর পরে)।
        local_hash = await self._generate_file_hash(upload_path)
        verify_path = upload_path + ".verify"
        dl = client.download_file(remote_path, verify_path)
        if dl.get("status") != "success":
            raise RuntimeError(f"durable verify-download failed: {dl.get('error', 'unknown')}")
        remote_hash = await self._generate_file_hash(verify_path)
        os.unlink(verify_path)
        if remote_hash != local_hash:
            raise RuntimeError("durable upload checksum mismatch — artifact NOT verified")

        # বাংলা: সফল verified upload → staged local copy দুটিই মুছে দাও
        if upload_path != local_path:
            os.unlink(upload_path)
        os.unlink(local_path)

        logger.info(f"backup {backup_id} verified+uploaded to {dest['scheme']}://{dest['bucket']}/{remote_path}")
        return f"{dest['scheme']}://{dest['bucket']}/{remote_path}"

    async def _materialize_durable_artifact(self, remote_location: str,
                                            expected_hash: str | None,
                                            backup_id: str) -> str:
        """Durable artifact স্থানীয়ভাবে আনা + checksum verify + decrypt।

        # বাংলা: restore rehearsal (#3164 verification) — durable destination
        # থেকে clean environment-এ ফেরানোর পথ। sha256 মিল না হলে restore
        # চলবেই না (fail-closed)।
        """
        dest = self.durable_destination
        if not dest:
            raise ValueError("durable destination not configured")
        prefix = f"{dest['scheme']}://{dest['bucket']}/"
        if not remote_location.startswith(prefix):
            raise ValueError(f"backup location is not a durable artifact: {remote_location}")
        remote_path = remote_location[len(prefix):]

        from database.storage_client import StorageClient
        provider = "supabase" if dest["scheme"] == "supabase-storage" else "s3"
        client = StorageClient(provider=provider)
        client.bucket_name = dest["bucket"]

        os.makedirs(DR_STAGING_DIR, exist_ok=True)
        target = os.path.join(DR_STAGING_DIR, f"{backup_id}.zip")
        dl = client.download_file(remote_path, target)
        if dl.get("status") != "success":
            raise RuntimeError(f"durable download failed: {dl.get('error', 'unknown')}")

        # বাংলা: এনক্রিপ্টেড হলে আগে decrypt — hash তুলনা হবে plaintext দিয়ে
        key = self._encryption_key()
        if key:
            from cryptography.fernet import Fernet
            cipher = Fernet(key)
            with open(target, "rb") as src:
                token = src.read()
            plain = cipher.decrypt(token)  # InvalidToken হলে fail-closed
            decrypted_path = target + ".plain"
            with open(decrypted_path, "wb") as out:
                out.write(plain)
            os.unlink(target)
            target = decrypted_path

        if expected_hash:
            actual = await self._generate_file_hash(target)
            if actual != expected_hash:
                os.unlink(target)
                raise RuntimeError("durable artifact checksum mismatch — restore refused")
        return target

    def apply_local_retention(self, retention_days: int | None = None) -> int:
        """Staging dir-এ পুরনো ফাইল মুছে ফেলা (retention policy, local side)।

        # বাংলা: remote retention bucket-lifecycle policy দিয়ে চালানোর নীতি
        # docs-এ documented; এখানে staged local residue-র retention।
        """
        days = retention_days if retention_days is not None else int(
            os.getenv("DR_BACKUP_RETENTION_DAYS", "30"))
        cutoff = time.time() - days * 86400
        removed = 0
        if os.path.isdir(DR_STAGING_DIR):
            for name in os.listdir(DR_STAGING_DIR):
                path = os.path.join(DR_STAGING_DIR, name)
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.unlink(path)
                        removed += 1
                except OSError:
                    continue
        return removed

    @staticmethod
    def _env_paths(env_var: str, defaults: list[str]) -> list[str]:
        """
        env var থেকে comma-separated paths পড়ে। env var না থাকলে বা empty হলে
        defaults ফেরত দেয়। এটি "zero-hardcoded" principle মেনে চলে — deployment-এর
        সময় প্রতিটা component-এর paths env var দিয়ে override করা যায়।
        """
        val = os.environ.get(env_var, "").strip()
        if not val:
            return defaults
        return [p.strip() for p in val.split(",") if p.strip()]

    async def initialize_recovery_plans(self):
        """Initialize disaster recovery plans in Redis."""
        try:
            existing_plans = await redis_manager.get(self.recovery_plan_key)
            if not existing_plans:
                await redis_manager.set(
                    self.recovery_plan_key,
                    json.dumps(self.default_recovery_plans),
                    ex=2592000,  # 30 days
                )
                logger.info("Default disaster recovery plans initialized")
        except Exception as e:
            logger.error(f"Error initializing recovery plans: {e}")

    async def create_backup(
        self,
        backup_type: str = "full",
        components: list[str] | None = None,
        location_override: str | None = None,
    ) -> BackupResult:
        """
        Create a system backup.

        Args:
            backup_type: Type of backup ('full', 'incremental', 'config_only', etc.)
            components: Specific components to back up (if None, uses defaults)
            location_override: Specific location for backup storage

        Returns:
            BackupResult containing backup information
        """
        start_time = datetime.utcnow()

        try:
            backup_id = f"backup_{int(start_time.timestamp())}_{os.urandom(4).hex()}"

            # Determine which components to back up
            if components is None:
                if backup_type == "full":
                    components = list(self.critical_components.keys())
                elif backup_type == "config_only":
                    components = ["configuration"]
                elif backup_type == "data_only":
                    components = ["database", "user_data"]
                else:
                    components = list(self.critical_components.keys())

            # Filter to only valid components
            valid_components = [comp for comp in components if comp in self.critical_components]

            logger.info(f"Starting backup {backup_id} for components: {valid_components}")

            # বাংলা (#3164) RUNTIME GUARD: durable destination কনফিগার না থাকলে
            # backup নিষিদ্ধ — ephemeral disk-এ লেখা artifact restart-এ হারায়।
            # dev/test escape hatch: DR_ALLOW_EPHEMERAL_BACKUP=true (স্পষ্ট warning সহ)।
            if not self.is_backup_destination_durable():
                if os.getenv("DR_ALLOW_EPHEMERAL_BACKUP", "").lower() == "true":
                    logger.warning(
                        "DR_ALLOW_EPHEMERAL_BACKUP=true — backup will be written to "
                        "EPHEMERAL local disk; artifacts are lost on restart (#3164)"
                    )
                else:
                    raise ValueError(
                        "Disaster-recovery backup BLOCKED: no durable destination configured. "
                        "Set DR_BACKUP_DESTINATION (e.g. supabase-storage://bucket/prefix or "
                        "s3://bucket/prefix) — ephemeral local storage is not a recovery "
                        "destination (#3164)."
                    )

            if self.durable_destination:
                # বাংলা: durable flow — আর্কাইভ staging-এ হয়, verified upload-এর
                # পর local copy মুছে ফেলা হয় (free-tier disk guard)।
                os.makedirs(DR_STAGING_DIR, exist_ok=True)
                backup_path = os.path.join(DR_STAGING_DIR, f"{backup_id}.zip")
            else:
                backup_location = location_override or getattr(
                    settings, "BACKUP_LOCATION", "/backups/")
                backup_path = os.path.join(backup_location, f"{backup_id}.zip")

            # Create backup archive
            size_bytes = await self._create_backup_archive(backup_path, valid_components)

            # Generate verification hash
            verification_hash = await self._generate_file_hash(backup_path)

            # বাংলা (#3164): durable destination থাকলে verified upload — সফল হলে
            # location হয় remote URI; staged local copy মুছে যায়।
            if self.durable_destination:
                final_location = await self._upload_to_durable(backup_path, backup_id)
            else:
                final_location = backup_path

            # Record backup completion
            duration = (datetime.utcnow() - start_time).total_seconds()

            backup_result = BackupResult(
                backup_id=backup_id,
                timestamp=start_time,
                size_bytes=size_bytes,
                location=final_location,
                status="success",
                verification_hash=verification_hash,
                components_backed_up=valid_components,
                duration_seconds=duration,
            )

            # Store backup result in history
            await self._store_backup_result(backup_result)

            # Update system state
            await self._update_system_state(
                {
                    "last_backup": start_time.isoformat(),
                    "backup_size": size_bytes,
                    "backup_location": backup_path,
                }
            )

            logger.info(f"Backup completed successfully: {backup_id}, size: {size_bytes} bytes")
            return backup_result

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            backup_result = BackupResult(
                backup_id=f"backup_{int(start_time.timestamp())}_failed",
                timestamp=start_time,
                size_bytes=0,
                location="",
                status="failed",
                verification_hash="",
                components_backed_up=components or [],
                duration_seconds=duration,
            )

            await self._store_backup_result(backup_result)
            return backup_result

    async def restore_from_backup(
        self,
        backup_id: str,
        recovery_plan: str = "full_restoration",
        components: list[str] | None = None,
    ) -> RecoveryResult:
        """
        Restore system from a backup using a specific recovery plan.

        Args:
            backup_id: ID of the backup to restore from
            recovery_plan: Name of the recovery plan to use
            components: Specific components to restore (overrides plan if provided)

        Returns:
            RecoveryResult containing restoration information
        """
        start_time = datetime.utcnow()

        try:
            recovery_id = f"recovery_{int(start_time.timestamp())}_{os.urandom(4).hex()}"

            # Get backup information
            backup_info = await self._get_backup_info(backup_id)
            if not backup_info:
                raise ValueError(f"Backup {backup_id} not found")

            logger.info(f"Starting recovery {recovery_id} from backup {backup_id}")

            # Determine components to restore
            if components:
                restore_components = components
            else:
                plans = await self._get_recovery_plans()
                plan_info = plans.get(recovery_plan)
                if plan_info:
                    restore_components = plan_info["components"]
                else:
                    restore_components = list(self.critical_components.keys())

            # Validate components exist in backup
            available_components = backup_info.get("components_backed_up", [])
            valid_components = [comp for comp in restore_components if comp in available_components]

            # Restore components in priority order
            restored_components = []
            # বাংলা (#3164): durable artifact হলে আগে স্থানীয়ভাবে আনা + checksum
            # verify + decrypt; মিল না হলে restore পুরোপুরি বন্ধ (fail-closed)।
            local_artifact = None
            if self.durable_destination and str(backup_info.get("location", "")).startswith(
                    DURABLE_SCHEMES):
                local_artifact = await self._materialize_durable_artifact(
                    backup_info["location"],
                    backup_info.get("verification_hash"),
                    backup_id,
                )
                restore_source = local_artifact
            else:
                restore_source = backup_info["location"]

            for component in self.recovery_priority_order:
                if component in valid_components:
                    success = await self._restore_component(component, restore_source)
                    if success:
                        restored_components.append(component)
            if local_artifact:
                try:
                    os.unlink(local_artifact)
                except OSError:
                    pass

            # Record recovery completion
            duration = (datetime.utcnow() - start_time).total_seconds()

            recovery_result = RecoveryResult(
                recovery_id=recovery_id,
                timestamp=start_time,
                backup_id=backup_id,
                status="success"
                if len(restored_components) == len(valid_components)
                else "partial",
                recovered_components=restored_components,
                duration_seconds=duration,
                notes=f"Restored {len(restored_components)} of {len(valid_components)} components",
            )

            # Store recovery result in history
            await self._store_recovery_result(recovery_result)

            # Update system state
            await self._update_system_state(
                {
                    "last_recovery": start_time.isoformat(),
                    "recovery_id": recovery_id,
                    "recovered_components": restored_components,
                }
            )

            logger.info(
                f"Recovery completed: {recovery_id}, restored {len(restored_components)} components"
            )
            return recovery_result

        except Exception as e:
            logger.error(f"Error during recovery: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            recovery_result = RecoveryResult(
                recovery_id=f"recovery_{int(start_time.timestamp())}_failed",
                timestamp=start_time,
                backup_id=backup_id,
                status="failed",
                recovered_components=[],
                duration_seconds=duration,
                notes=f"Recovery failed: {e!s}",
            )

            await self._store_recovery_result(recovery_result)
            return recovery_result

    async def _create_backup_archive(self, archive_path: str, components: list[str]) -> int:
        """Create a backup archive for specified components."""
        try:
            os.makedirs(os.path.dirname(archive_path), exist_ok=True)

            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for component in components:
                    if component in self.critical_components:
                        comp_info = self.critical_components[component]
                        paths = comp_info["paths"]

                        for path_str in paths:
                            path = Path(path_str)
                            if path.exists():
                                if path.is_file():
                                    # Add single file
                                    zipf.write(str(path), f"{component}/{path.name}")
                                elif path.is_dir():
                                    # Add directory contents
                                    for file_path in path.rglob("*"):
                                        if file_path.is_file():
                                            arc_name = f"{component}/{file_path.relative_to(path)}"
                                            zipf.write(str(file_path), arc_name)

            # Return file size
            return os.path.getsize(archive_path)
        except Exception as e:
            logger.error(f"Error creating backup archive: {e}")
            raise

    async def _restore_component(self, component: str, backup_path: str) -> bool:
        """Restore a specific component from backup."""
        try:
            if component not in self.critical_components:
                logger.warning(f"Unknown component: {component}")
                return False

            comp_info = self.critical_components[component]
            restore_method = comp_info["restore_method"]

            if restore_method == "skip":
                logger.info(f"Skipping restoration of {component} (restore_method: skip)")
                return True

            # Extract component from backup
            with zipfile.ZipFile(backup_path, "r") as zipf:
                # Get all files for this component
                comp_files = [f for f in zipf.namelist() if f.startswith(f"{component}/")]

                if not comp_files:
                    logger.warning(f"No files found for component {component} in backup")
                    return False

                # Extract files to destination
                dest_path = comp_info["paths"][0]  # Use first path as destination
                os.makedirs(dest_path, exist_ok=True)

                for file_in_zip in comp_files:
                    zipf.extract(file_in_zip, dest_path)

            logger.info(f"Successfully restored component: {component}")
            return True

        except Exception as e:
            logger.error(f"Error restoring component {component}: {e}")
            return False

    async def _generate_file_hash(self, file_path: str) -> str:
        """Generate SHA-256 hash for file verification."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error generating file hash: {e}")
            return ""

    async def _store_backup_result(self, result: BackupResult):
        """Store backup result in Redis."""
        try:
            result_data = {
                "backup_id": result.backup_id,
                "timestamp": result.timestamp.isoformat(),
                "size_bytes": result.size_bytes,
                "location": result.location,
                "status": result.status,
                "verification_hash": result.verification_hash,
                "components_backed_up": result.components_backed_up,
                "duration_seconds": result.duration_seconds,
            }

            # Get existing backups
            existing_backups = await redis_manager.get(self.backup_history_key)
            if existing_backups:
                backups_list = json.loads(existing_backups)
            else:
                backups_list = []

            # Add new backup
            backups_list.append(result_data)

            # Keep only the last N backups
            max_backups = 50
            if len(backups_list) > max_backups:
                backups_list = backups_list[-max_backups:]

            await redis_manager.set(
                self.backup_history_key,
                json.dumps(backups_list),
                ex=2592000,  # 30 days
            )
        except Exception as e:
            logger.error(f"Error storing backup result: {e}")

    async def _store_recovery_result(self, result: RecoveryResult):
        """Store recovery result in Redis."""
        try:
            result_data = {
                "recovery_id": result.recovery_id,
                "timestamp": result.timestamp.isoformat(),
                "backup_id": result.backup_id,
                "status": result.status,
                "recovered_components": result.recovered_components,
                "duration_seconds": result.duration_seconds,
                "notes": result.notes,
            }

            # Get existing recoveries
            existing_recoveries = await redis_manager.get(self.recovery_history_key)
            if existing_recoveries:
                recoveries_list = json.loads(existing_recoveries)
            else:
                recoveries_list = []

            # Add new recovery
            recoveries_list.append(result_data)

            # Keep only the last N recoveries
            max_recoveries = 50
            if len(recoveries_list) > max_recoveries:
                recoveries_list = recoveries_list[-max_recoveries:]

            await redis_manager.set(
                self.recovery_history_key,
                json.dumps(recoveries_list),
                ex=2592000,  # 30 days
            )
        except Exception as e:
            logger.error(f"Error storing recovery result: {e}")

    async def _get_backup_info(self, backup_id: str) -> dict[str, Any] | None:
        """Get information about a specific backup."""
        try:
            existing_backups = await redis_manager.get(self.backup_history_key)
            if not existing_backups:
                return None

            backups_list = json.loads(existing_backups)
            for backup in backups_list:
                if backup["backup_id"] == backup_id:
                    return backup

            return None
        except Exception as e:
            logger.error(f"Error getting backup info: {e}")
            return None

    async def _get_recovery_plans(self) -> dict[str, Any]:
        """Get current recovery plans."""
        try:
            plans_json = await redis_manager.get(self.recovery_plan_key)
            if plans_json:
                return json.loads(plans_json)
            else:
                return self.default_recovery_plans
        except Exception as e:
            logger.error(f"Error getting recovery plans: {e}")
            return self.default_recovery_plans

    async def _update_system_state(self, state_updates: dict[str, Any]):
        """Update system state with recovery-related information."""
        try:
            # Get current state
            current_state = await redis_manager.get(self.system_state_key)
            if current_state:
                state = json.loads(current_state)
            else:
                state = {}

            # Update with new information
            state.update(state_updates)
            state["last_updated"] = datetime.utcnow().isoformat()

            await redis_manager.set(
                self.system_state_key,
                json.dumps(state),
                ex=86400,  # 24 hours
            )
        except Exception as e:
            logger.error(f"Error updating system state: {e}")

    async def get_backup_schedule_recommendations(self) -> dict[str, Any]:
        """
        Generate recommendations for backup scheduling based on system usage.

        Returns:
            Dictionary with backup schedule recommendations
        """
        try:
            # Analyze system state and usage patterns to recommend backup schedule
            system_state = await redis_manager.get(self.system_state_key)
            if system_state:
                state = json.loads(system_state)
            else:
                state = {}

            # Default recommendations
            recommendations = {
                "full_backup_frequency": "daily",
                "incremental_backup_frequency": "hourly",
                "retention_period_days": 30,
                "offsite_replication": True,
                "backup_windows": ["02:00-04:00", "14:00-16:00"],  # Low usage times
                "critical_components_schedule": {
                    "configuration": "every_change",
                    "database": "hourly",
                    "user_data": "daily",
                },
            }

            # Adjust based on system characteristics
            if state.get("high_transaction_volume"):
                recommendations["incremental_backup_frequency"] = "every_15_minutes"

            if state.get("regulatory_requirements", {}).get("strict_data_retention"):
                recommendations["retention_period_days"] = 90

            return recommendations

        except Exception as e:
            logger.error(f"Error generating backup schedule recommendations: {e}")
            return {
                "full_backup_frequency": "daily",
                "incremental_backup_frequency": "hourly",
                "retention_period": 30,
                "offsite_replication": True,
            }

    async def verify_backup_integrity(self, backup_id: str) -> dict[str, Any]:
        """
        Verify the integrity of a backup.

        Args:
            backup_id: ID of the backup to verify

        Returns:
            Dictionary with verification results
        """
        try:
            backup_info = await self._get_backup_info(backup_id)
            if not backup_info:
                return {"status": "not_found", "message": f"Backup {backup_id} not found"}

            backup_path = backup_info["location"]
            stored_hash = backup_info["verification_hash"]

            # Recalculate hash
            current_hash = await self._generate_file_hash(backup_path)

            # Verify file structure
            try:
                with zipfile.ZipFile(backup_path, "r") as zipf:
                    file_list = zipf.namelist()
                    is_valid_structure = len(file_list) > 0
            except zipfile.BadZipFile:
                is_valid_structure = False

            verification_result = {
                "backup_id": backup_id,
                "status": "verified"
                if (stored_hash == current_hash and is_valid_structure)
                else "corrupted",
                "hash_match": stored_hash == current_hash,
                "structure_valid": is_valid_structure,
                "file_count": len(file_list) if is_valid_structure else 0,
                "size_match": os.path.getsize(backup_path) == backup_info["size_bytes"],
                "timestamp": datetime.utcnow().isoformat(),
            }

            return verification_result

        except Exception as e:
            logger.error(f"Error verifying backup integrity: {e}")
            return {
                "backup_id": backup_id,
                "status": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


# Global instance
disaster_recovery_agent = DisasterRecoveryAgent()

# Initialize recovery plan on module load — শুধুমাত্র একটা event loop চলমান থাকলেই টাস্ক শিডিউল করা হয়;
# বাংলা: import-time-এ event loop না থাকলে RuntimeError এড়ানো হয়, আর টাস্কের রেফারেন্স ট্র্যাক করে
# রাখা হয় যাতে GC হয়ে মাঝপথে বাতিল না হয়ে যায় (RUF006)।
try:
    track_task(
        asyncio.get_running_loop().create_task(disaster_recovery_agent.initialize_recovery_plans())
    )
except RuntimeError:
    logger.debug(
        "No running event loop at import time; skipping eager recovery plan init "
        "(call initialize_recovery_plans() explicitly during app startup instead)."
    )
