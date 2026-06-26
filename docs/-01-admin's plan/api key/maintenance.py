#!/usr/bin/env python3
"""
SupremeAI 2.0 — API Key System Maintenance Script
Run daily via cron or Celery beat.
"""
import argparse
import sys
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

# Add project root to path
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from core.config import settings
from core.database import get_db_session
from core.rate_limiter import get_rate_limiter
from core.notifications import send_notification
from models.api_key import APIKey, KeyStatus, KeyQuotaAlert, APIKeyUsage


def expire_keys(db, dry_run: bool = False) -> int:
    """Expire keys past their expiration date."""
    now = datetime.utcnow()
    expired = db.query(APIKey).filter(
        APIKey.status == KeyStatus.ACTIVE.value,
        APIKey.expires_at.isnot(None),
        APIKey.expires_at <= now
    ).all()

    count = 0
    for key in expired:
        if not dry_run:
            key.status = KeyStatus.EXPIRED.value
            send_notification(
                user_id=key.user_id,
                title="API Key Expired",
                message=f"Your key '{key.name}' has expired.",
                channels=["email", "in_app"],
            )
        count += 1
        logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Expired key: {key.id}")

    if not dry_run:
        db.commit()
    return count


def reset_quotas(db, dry_run: bool = False) -> int:
    """Reset monthly quotas (run on 1st of month)."""
    now = datetime.utcnow()
    if now.day != 1:
        logger.info("Not 1st of month, skipping quota reset")
        return 0

    keys = db.query(APIKey).filter(
        APIKey.status.in_([KeyStatus.ACTIVE.value, KeyStatus.SUSPENDED.value])
    ).all()

    rate_limiter = get_rate_limiter()
    count = 0

    for key in keys:
        if not dry_run:
            key.quota_used = 0
            key.quota_reset_at = now
            rate_limiter.reset_quota(str(key.id))

            # Reactivate if suspended due to quota
            if key.status == KeyStatus.SUSPENDED.value and key.revoked_reason and "quota" in key.revoked_reason.lower():
                key.status = KeyStatus.ACTIVE.value
                key.revoked_reason = None
                key.revoked_at = None
                key.revoked_by = None
        count += 1

    if not dry_run:
        db.commit()
    return count


def cleanup_old_usage(db, dry_run: bool = False, days: int = 395) -> int:
    """Remove usage records older than 13 months."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # For partitioned tables, drop old partitions instead
    # This is a simplified version
    old_records = db.query(APIKeyUsage).filter(APIKeyUsage.created_at < cutoff).all()
    count = len(old_records)

    if not dry_run and count > 0:
        for record in old_records:
            db.delete(record)
        db.commit()

    logger.info(f"{'[DRY-RUN] ' if dry_run else ''}Cleaned up {count} old usage records")
    return count


def generate_report(db) -> dict:
    """Generate daily system report."""
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    total_keys = db.query(APIKey).count()
    active_keys = db.query(APIKey).filter(APIKey.status == KeyStatus.ACTIVE.value).count()

    # Yesterday's usage
    yesterday_requests = db.query(APIKeyUsage).filter(APIKeyUsage.created_at >= yesterday).count()
    yesterday_tokens = db.query(APIKeyUsage).filter(
        APIKeyUsage.created_at >= yesterday
    ).with_entities(APIKeyUsage.tokens_total).all()
    total_tokens = sum(t[0] for t in yesterday_tokens) if yesterday_tokens else 0

    # Top users
    top_users = db.query(
        APIKeyUsage.user_id,
        db.func.count(APIKeyUsage.id).label('requests')
    ).filter(APIKeyUsage.created_at >= yesterday).group_by(APIKeyUsage.user_id).order_by(db.func.count(APIKeyUsage.id).desc()).limit(5).all()

    report = {
        "date": now.isoformat(),
        "keys": {
            "total": total_keys,
            "active": active_keys,
            "inactive": total_keys - active_keys,
        },
        "usage_24h": {
            "requests": yesterday_requests,
            "tokens": total_tokens,
        },
        "top_users": [{"user_id": str(u.user_id), "requests": u.requests} for u in top_users],
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="SupremeAI API Key System Maintenance")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--task", choices=["expire", "reset-quotas", "cleanup", "report", "all"], default="all", help="Task to run")
    parser.add_argument("--cleanup-days", type=int, default=395, help="Days to keep usage records")
    args = parser.parse_args()

    db = next(get_db_session())

    try:
        if args.task in ["expire", "all"]:
            count = expire_keys(db, args.dry_run)
            logger.info(f"Expired {count} keys")

        if args.task in ["reset-quotas", "all"]:
            count = reset_quotas(db, args.dry_run)
            logger.info(f"Reset quotas for {count} keys")

        if args.task in ["cleanup", "all"]:
            count = cleanup_old_usage(db, args.dry_run, args.cleanup_days)
            logger.info(f"Cleaned up {count} old records")

        if args.task in ["report", "all"]:
            report = generate_report(db)
            print("
" + "="*50)
            print("DAILY REPORT")
            print("="*50)
            print(f"Date: {report['date']}")
            print(f"Total Keys: {report['keys']['total']} (Active: {report['keys']['active']})")
            print(f"24h Usage: {report['usage_24h']['requests']} requests, {report['usage_24h']['tokens']} tokens")
            print(f"Top Users: {len(report['top_users'])}")
            print("="*50)

    finally:
        db.close()


if __name__ == "__main__":
    main()
