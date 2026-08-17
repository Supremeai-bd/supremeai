# Deployment Guide

## Overview

SupremeAI 2.0 supports multi-platform deployment with zero-cost infrastructure. This guide covers deployment to Cloud Run, Render, Vercel, and Firebase.

## Prerequisites

- Google Cloud SDK installed and authenticated
- Docker installed and running
- Environment variables configured (see [Getting Started](getting-started.md))

## Deployment Platforms

### 1. Google Cloud Run (Primary)

```bash
# Deploy backend to Cloud Run
gcloud run deploy supremeai-backend \
  --source ./backend \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars-file backend/.env.yaml
```

### 2. Render (Backup)

```bash
# Deploy via Render CLI
render deploy --service-id srv-xxxxx

# Or via Git push
git push render main
```

### 3. Vercel (Frontend)

```bash
# Deploy frontend
cd apps/studio-client
vercel --prod

# Deploy with environment
vercel --prod --env production
```

### 4. Firebase (Hosting + Auth)

```bash
# Deploy to Firebase
firebase deploy --only hosting,firestore,functions

# Deploy specific targets
firebase deploy --only hosting
firebase deploy --only firestore
```

## Multi-Cloud Secret Sync

Always synchronize secrets across all platforms:

```bash
# Sync secrets to all platforms
python scripts/sync_all_platforms_env.py

# Sync to specific platform
python scripts/sync_all_platforms_env.py --platform render
python scripts/sync_all_platforms_env.py --platform vercel
python scripts/sync_all_platforms_env.py --platform gcp
```

## Blue-Green Deployment

SupremeAI uses blue-green deployment for zero-downtime releases:

1. Deploy new version to inactive environment
2. Run health checks on new version
3. Switch traffic to new version
4. Monitor for 5 minutes
5. Decommission old version

## Health Checks

### Backend Health

```bash
# Basic health check
curl https://your-backend-url/health

# Aggregated health check
curl https://your-backend-url/health/aggregated

# Detailed health check
curl https://your-backend-url/health/detailed
```

### Frontend Health

```bash
# Check if frontend is accessible
curl -I https://your-frontend-url.com
```

## Rollback

If deployment fails, rollback immediately:

```bash
# Rollback Cloud Run
gcloud run services describe supremeai-backend --region us-central1

# Rollback Render
render rollback --service-id srv-xxxxx --clear-cache

# Rollback Vercel
vercel rollback --debug
```

## Monitoring

- **Uptime**: 99.85% (target: 99.9%)
- **Response Time**: <800ms (target: <500ms)
- **Error Rate**: <0.4% (target: <0.1%)
- **MTTR**: 8 minutes (target: 5 minutes)

## Zero-Cost Infrastructure

| Service | Provider | Free Tier | Monthly Cost |
|---------|----------|-----------|--------------|
| Cloud Run | GCP | Always Free | $0 |
| Firebase | Google | Free Tier | $0 |
| Render | Render | 750h/month | $0 |
| Upstash Redis | Upstash | 10k req/day | $0 |
| Cloudflare | Cloudflare | Free Tier | $0 |
| **Total** | | | **$0/মাস** |
