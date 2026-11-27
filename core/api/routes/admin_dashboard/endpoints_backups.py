"""Backup + emergency deployment endpoints
(POST /admin-api/emergency-deploy, POST /admin-api/backup,
GET/POST /admin-api/backups, POST /admin-api/backups/{backup_id}/restore)."""

import json
import os
import shutil

from fastapi import HTTPException

from api.routes.admin_dashboard import router
from core.monitoring.logging_config import logger
from core.utils.time_utils import utc_now

# বাংলা মন্তব্য (Step 0, fail-honest): আগে কিছু না করেই "success" বলত। আসল
# deploy pipeline wired না হওয়া পর্যন্ত সৎভাবে 501 ফেরত দেয়।
NOT_WIRED_DETAIL = "not wired: {what} is not implemented on this backend yet"


@router.post("/emergency-deploy")
def emergency_deploy():
    logger.warning("Emergency deployment requested via Admin Dashboard (not wired)")
    raise HTTPException(status_code=501, detail=NOT_WIRED_DETAIL.format(what="emergency deploy"))


# Only non-secret data files. Secrets live in Infisical / the host env, never on disk backups.
BACKUP_SOURCE_FILES: tuple[str, ...] = ("data/constitutional_rules.db", "data/users.json")


@router.post("/backup")
def trigger_backup():
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backups/backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    # বাংলা মন্তব্য (security): `.env` (সিক্রেট) আর কখনো ব্যাকআপ ফোল্ডারে কপি হয় না।
    for fname in BACKUP_SOURCE_FILES:
        if os.path.exists(fname):
            try:
                shutil.copy2(fname, os.path.join(backup_dir, os.path.basename(fname)))
            except Exception as exc:
                logger.warning(f"Backup skipped for {fname}: {exc}")
    logger.info(f"Backup created at {backup_dir}")
    return {"status": "success", "backup_path": backup_dir}


@router.get("/backups")
def get_backups():
    backups_list = []
    if os.path.exists("backups"):
        for b_name in os.listdir("backups"):
            b_path = os.path.join("backups", b_name)
            if os.path.isdir(b_path):
                # Calculate size
                total_size = sum(
                    os.path.getsize(os.path.join(b_path, f))
                    for f in os.listdir(b_path)
                    if os.path.isfile(os.path.join(b_path, f))
                )
                # Size string
                size_mb = total_size / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB" if size_mb > 0 else "< 1 MB"

                # Parse timestamp from name
                ts = b_name.replace("backup_", "")
                if len(ts) == 15:  # YYYYMMDD_HHMMSS
                    ts_formatted = (
                        f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}"
                    )
                else:
                    ts_formatted = "Unknown"

                backups_list.append(
                    {
                        "id": b_name,
                        "timestamp": ts_formatted,
                        "size": size_str,
                        "type": "manual",
                        "status": "completed",
                        "retention": "permanent",
                    }
                )
    backups_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"backups": backups_list}


# CI FIX: frontend hooks.ts:366 calls POST /admin-api/backups to create a
# backup. Added POST alias.
@router.post("/backups")
def create_backup():
    """Create a manual backup — same real copy as POST /backup (no secrets)."""
    try:
        result = trigger_backup()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    backup_dir = result["backup_path"]
    with open(os.path.join(backup_dir, "manifest.json"), "w") as f:
        json.dump({"timestamp": os.path.basename(backup_dir), "type": "manual"}, f)
    return {"status": "success", "backup_name": os.path.basename(backup_dir)}


# CI FIX: frontend hooks.ts:453 calls POST /admin-api/backups/{id}/restore
# to trigger a restore. Added POST alias.
@router.post("/backups/{backup_id}/restore")
def restore_backup(backup_id: str):
    """Restore is not implemented — fail honest instead of a fake "queued"."""
    if "/" in backup_id or "\\" in backup_id or backup_id.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid backup id")
    backup_dir = f"backups/{backup_id}"
    if not os.path.exists(backup_dir):
        raise HTTPException(status_code=404, detail=f"Backup '{backup_id}' not found")
    raise HTTPException(status_code=501, detail=NOT_WIRED_DETAIL.format(what="backup restore"))
