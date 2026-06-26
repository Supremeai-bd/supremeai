# SupremeAI 2.0 — API Key Management System

## 📁 File Structure

```
supremeai-apikey-system/
├── PLAN.md                                    # Full architecture & plan
├── backend/
│   ├── models/
│   │   └── api_key.py                         # SQLAlchemy models (APIKey, APIKeyUsage, APIKeyEvent)
│   ├── core/
│   │   ├── security.py                        # Key generation, hashing, validation
│   │   ├── rate_limiter.py                    # Redis sliding window rate limiter
│   │   ├── middleware.py                    # FastAPI auth middleware
│   │   └── celery_tasks.py                    # Scheduled maintenance tasks
│   ├── api/
│   │   └── keys.py                            # FastAPI router (CRUD + admin)
│   └── tests/
│       └── test_api_keys.py                   # Comprehensive test suite
├── frontend/
│   └── ApiKeyManager.tsx                      # React component for Studio Admin
├── scripts/
│   ├── deploy-apikey-system.sh               # One-click deployment script
│   └── maintenance.py                         # Daily maintenance CLI
└── docker-compose-additions.yml               # Redis + Celery services
```

## 🚀 Quick Start

### 1. Deploy the system
```bash
chmod +x scripts/deploy-apikey-system.sh
./scripts/deploy-apikey-system.sh staging
```

### 2. Run maintenance manually
```bash
python scripts/maintenance.py --task all
# Or dry-run to preview:
python scripts/maintenance.py --task all --dry-run
```

### 3. Run tests
```bash
cd backend
poetry run pytest tests/test_api_keys.py -v
```

## 🔑 API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/keys` | Create new API key | JWT |
| GET | `/api/v1/keys` | List all keys | JWT |
| GET | `/api/v1/keys/{id}` | Get key details | JWT |
| PATCH | `/api/v1/keys/{id}` | Update key settings | JWT |
| POST | `/api/v1/keys/{id}/rotate` | Rotate key (new key, old revoked) | JWT |
| POST | `/api/v1/keys/{id}/revoke` | Revoke key immediately | JWT |
| GET | `/api/v1/keys/{id}/usage` | Get usage statistics | JWT |
| GET | `/api/v1/keys/{id}/events` | Get audit events | JWT |
| GET | `/api/v1/keys/admin/all` | Admin: list all keys | Admin scope |
| POST | `/api/v1/keys/admin/{id}/suspend` | Admin: suspend key | Admin scope |
| POST | `/api/v1/keys/admin/{id}/reactivate` | Admin: reactivate key | Admin scope |
| GET | `/api/v1/keys/admin/stats` | Admin: global stats | Admin scope |

## 🔒 Security Features

- **bcrypt hashing**: Keys stored as hashes only (cost factor 12)
- **Prefix indexing**: Fast lookup without exposing full keys
- **Sliding window rate limiting**: Redis-based RPM + RPD limits
- **IP whitelisting**: Optional CIDR-based access control
- **Quota enforcement**: Monthly token limits with auto-suspend
- **Audit logging**: Every key action logged immutably
- **Auto-expiry**: Keys expire after configured lifetime
- **Auto-rotation reminders**: 7-day expiry warnings
- **Suspicious usage detection**: Alerts on 10x normal usage

## 📊 Monitoring

- **Prometheus metrics**: Key validation latency, rate limit hits, quota usage
- **Sentry integration**: Error tracking for auth failures
- **Celery Flower**: Task monitoring at `/flower`
- **Redis monitoring**: `redis-cli monitor` or Redis Insight

## 🛠️ Maintenance Schedule

| Task | Frequency | Celery Task |
|------|-----------|-------------|
| Expire old keys | Daily midnight | `expire_keys_task` |
| Reset quotas | 1st of month | `reset_monthly_quotas_task` |
| Quota alerts | Daily noon | `quota_alert_task` |
| Rotation reminders | Weekly Sunday | `rotate_expiring_keys_task` |
| Unused key cleanup | Weekly Sunday | `cleanup_unused_keys_task` |
| Usage data cleanup | Monthly | `cleanup_old_usage` (manual) |
