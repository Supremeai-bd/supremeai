"""
SupremeAI 2.0 — API Key Maintenance Celery Tasks
Scheduled tasks for key lifecycle management, quota resets, and alerts.
"""
from datetime import datetime, timedelta
from typing import List

from celery import Celery
from celery.schedules import crontab
from loguru import logger

from core.database import get_db_session
from core.rate_limiter import get_rate_limiter
from core.notifications import send_notification
from models.api_key import APIKey, KeyStatus, KeyQuotaAlert

# Celery app (configured in core/celery_app.py)
celery_app = Celery('supremeai_apikey_tasks')


# ═══════════════════════════════════════════════════════════════
# DAILY TASKS
# ═══════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3)
def expire_keys_task(self):
    """
    Daily task: Expire keys past their expiration date.
    Runs at 00:00 UTC.
    """
    logger.info("Running key expiration task")
    db = next(get_db_session())

    try:
        now = datetime.utcnow()

        # Find expired keys
        expired_keys = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.expires_at.isnot(None),
            APIKey.expires_at <= now
        ).all()

        count = 0
        for key in expired_keys:
            key.status = KeyStatus.EXPIRED.value

            # Send notification
            send_notification.delay(
                user_id=key.user_id,
                title="API Key Expired",
                message=f"Your API key '{key.name}' has expired. Please rotate it to continue using the API.",
                channels=["email", "in_app"],
            )

            logger.info(f"Key expired: {key.id} ({key.name})")
            count += 1

        db.commit()
        logger.info(f"Expired {count} keys")

        return {"expired_count": count}

    except Exception as exc:
        logger.exception("Key expiration task failed")
        db.rollback()
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def reset_monthly_quotas_task(self):
    """
    Monthly task: Reset quota counters on 1st of month.
    Runs at 00:00 UTC on 1st of each month.
    """
    logger.info("Running monthly quota reset task")
    db = next(get_db_session())
    rate_limiter = get_rate_limiter()

    try:
        now = datetime.utcnow()

        # Only run on 1st of month
        if now.day != 1:
            logger.info("Not 1st of month, skipping quota reset")
            return {"skipped": True}

        # Reset all active keys
        keys = db.query(APIKey).filter(
            APIKey.status.in_([KeyStatus.ACTIVE.value, KeyStatus.SUSPENDED.value])
        ).all()

        count = 0
        for key in keys:
            key.quota_used = 0
            key.quota_reset_at = now

            # Reset Redis quota counter
            rate_limiter.reset_quota(str(key.id))

            # If suspended due to quota, reactivate
            if key.status == KeyStatus.SUSPENDED.value:
                # Check if it was suspended due to quota (not admin action)
                if key.revoked_reason and "quota" in key.revoked_reason.lower():
                    key.status = KeyStatus.ACTIVE.value
                    key.revoked_reason = None
                    key.revoked_at = None
                    key.revoked_by = None

            count += 1

        db.commit()
        logger.info(f"Reset quotas for {count} keys")

        return {"reset_count": count}

    except Exception as exc:
        logger.exception("Quota reset task failed")
        db.rollback()
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def quota_alert_task(self):
    """
    Daily task: Send quota alerts for keys approaching limits.
    Runs at 12:00 UTC.
    """
    logger.info("Running quota alert task")
    db = next(get_db_session())

    try:
        # 80% alert
        keys_80 = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.quota_used >= (APIKey.monthly_quota * 0.8),
            APIKey.quota_used < (APIKey.monthly_quota * 0.95),
        ).all()

        for key in keys_80:
            # Check if alert already sent
            existing = db.query(KeyQuotaAlert).filter(
                KeyQuotaAlert.key_id == key.id,
                KeyQuotaAlert.alert_type == "80_percent"
            ).first()

            if not existing:
                send_notification.delay(
                    user_id=key.user_id,
                    title="API Key Quota Alert (80%)",
                    message=f"Your key '{key.name}' has used 80% of its monthly quota ({key.quota_used:,}/{key.monthly_quota:,} tokens).",
                    channels=["email", "in_app"],
                )

                alert = KeyQuotaAlert(key_id=key.id, alert_type="80_percent")
                db.add(alert)
                logger.info(f"Sent 80% quota alert for key {key.id}")

        # 95% alert
        keys_95 = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.quota_used >= (APIKey.monthly_quota * 0.95),
            APIKey.quota_used < APIKey.monthly_quota,
        ).all()

        for key in keys_95:
            existing = db.query(KeyQuotaAlert).filter(
                KeyQuotaAlert.key_id == key.id,
                KeyQuotaAlert.alert_type == "95_percent"
            ).first()

            if not existing:
                send_notification.delay(
                    user_id=key.user_id,
                    title="API Key Quota Alert (95%)",
                    message=f"Your key '{key.name}' has used 95% of its monthly quota. It will be suspended when quota is reached.",
                    channels=["email", "in_app"],
                    priority="high",
                )

                alert = KeyQuotaAlert(key_id=key.id, alert_type="95_percent")
                db.add(alert)
                logger.info(f"Sent 95% quota alert for key {key.id}")

        # 100% alert + suspend
        keys_100 = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.quota_used >= APIKey.monthly_quota,
        ).all()

        for key in keys_100:
            existing = db.query(KeyQuotaAlert).filter(
                KeyQuotaAlert.key_id == key.id,
                KeyQuotaAlert.alert_type == "100_percent"
            ).first()

            if not existing:
                # Suspend key
                key.status = KeyStatus.SUSPENDED.value
                key.revoked_reason = "Monthly quota exceeded"
                key.revoked_at = datetime.utcnow()

                send_notification.delay(
                    user_id=key.user_id,
                    title="API Key Suspended — Quota Exceeded",
                    message=f"Your key '{key.name}' has been suspended because it exceeded its monthly quota of {key.monthly_quota:,} tokens.",
                    channels=["email", "in_app", "discord"],
                    priority="high",
                )

                alert = KeyQuotaAlert(key_id=key.id, alert_type="100_percent")
                db.add(alert)
                logger.info(f"Suspended key {key.id} due to quota exhaustion")

        db.commit()
        return {"alerts_sent": len(keys_80) + len(keys_95) + len(keys_100)}

    except Exception as exc:
        logger.exception("Quota alert task failed")
        db.rollback()
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# WEEKLY TASKS
# ═══════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3)
def rotate_expiring_keys_task(self):
    """
    Weekly task: Notify owners of keys expiring within 7 days.
    Runs on Sundays at 10:00 UTC.
    """
    logger.info("Running key rotation reminder task")
    db = next(get_db_session())

    try:
        now = datetime.utcnow()
        warning_date = now + timedelta(days=7)

        expiring_keys = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.expires_at.isnot(None),
            APIKey.expires_at <= warning_date,
            APIKey.expires_at > now,
        ).all()

        for key in expiring_keys:
            days_left = (key.expires_at - now).days

            send_notification.delay(
                user_id=key.user_id,
                title=f"API Key Expires in {days_left} Days",
                message=f"Your key '{key.name}' will expire on {key.expires_at.strftime('%Y-%m-%d')}. Please rotate it to avoid service interruption.",
                channels=["email", "in_app"],
            )

            logger.info(f"Sent expiry reminder for key {key.id} ({days_left} days left)")

        return {"reminders_sent": len(expiring_keys)}

    except Exception as exc:
        logger.exception("Key rotation reminder task failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def cleanup_unused_keys_task(self):
    """
    Weekly task: Notify owners of keys unused for 30 days.
    Keys unused for 37 days are auto-expired.
    """
    logger.info("Running unused key cleanup task")
    db = next(get_db_session())

    try:
        now = datetime.utcnow()

        # Keys unused for 30 days (warning)
        warning_keys = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.last_used_at.isnot(None),
            APIKey.last_used_at <= now - timedelta(days=30),
            APIKey.last_used_at > now - timedelta(days=37),
        ).all()

        for key in warning_keys:
            days_unused = (now - key.last_used_at).days

            send_notification.delay(
                user_id=key.user_id,
                title="API Key Unused for 30 Days",
                message=f"Your key '{key.name}' has not been used for {days_unused} days. It will be auto-expired in 7 days if unused.",
                channels=["email"],
            )

        # Keys unused for 37 days (auto-expire)
        expire_keys = db.query(APIKey).filter(
            APIKey.status == KeyStatus.ACTIVE.value,
            APIKey.last_used_at.isnot(None),
            APIKey.last_used_at <= now - timedelta(days=37),
        ).all()

        for key in expire_keys:
            key.status = KeyStatus.EXPIRED.value
            key.revoked_reason = "Auto-expired: unused for 37+ days"
            key.revoked_at = now

            send_notification.delay(
                user_id=key.user_id,
                title="API Key Auto-Expired",
                message=f"Your key '{key.name}' has been auto-expired due to inactivity (37+ days unused).",
                channels=["email", "in_app"],
            )

            logger.info(f"Auto-expired key {key.id} due to inactivity")

        db.commit()
        return {"warnings_sent": len(warning_keys), "auto_expired": len(expire_keys)}

    except Exception as exc:
        logger.exception("Unused key cleanup task failed")
        db.rollback()
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# CELERY BEAT SCHEDULE
# ═══════════════════════════════════════════════════════════════

celery_app.conf.beat_schedule = {
    'expire-keys-daily': {
        'task': 'tasks.api_key_tasks.expire_keys_task',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'reset-quotas-monthly': {
        'task': 'tasks.api_key_tasks.reset_monthly_quotas_task',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),  # 1st of month
    },
    'quota-alerts-daily': {
        'task': 'tasks.api_key_tasks.quota_alert_task',
        'schedule': crontab(hour=12, minute=0),  # Daily at noon
    },
    'rotate-reminders-weekly': {
        'task': 'tasks.api_key_tasks.rotate_expiring_keys_task',
        'schedule': crontab(hour=10, minute=0, day_of_week=0),  # Sunday 10am
    },
    'cleanup-unused-weekly': {
        'task': 'tasks.api_key_tasks.cleanup_unused_keys_task',
        'schedule': crontab(hour=11, minute=0, day_of_week=0),  # Sunday 11am
    },
}
