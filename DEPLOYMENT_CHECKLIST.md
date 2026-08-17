# SupremeAI - Deployment Checklist

**তারিখ:** 11 August 2026  
**Purpose:** Production deployment verification checklist

---

## Pre-Deployment Checklist

### ✅ Code Changes Completed
- [x] Verified CORS configuration (render.yaml has USER_CORS_ORIGINS and ADMIN_CORS_ORIGINS)
- [x] Verified frontend .env exists (apps/studio-client/.env)
- [x] Verified Firebase rewrites configured (firebase.json)
- [x] Added FIREBASE_SERVICE_ACCOUNT_JSON to render.yaml (both services, sync: false)
- [x] Updated .gitignore to prevent .env leakage (line 18-19, 22-23, 29)

---

## Environment Variables Checklist

### Render Dashboard - supremeai-backend
```
Required Variables:
- [ ] PORT = 8080
- [ ] ENV = production
- [ ] SERVICE_ROLE = user
- [ ] CORS_ORIGINS = ["https://supremeai-studio-client.onrender.com",...]
- [ ] USER_CORS_ORIGINS = ["https://supremeai-studio-client.onrender.com",...]
- [ ] ADMIN_CORS_ORIGINS = []
- [ ] ALLOWED_HOSTS = supremeai-backend.onrender.com
- [ ] FIREBASE_SERVICE_ACCOUNT_JSON = (sync: false - verify in dashboard)

Critical Secrets (sync: false - verify they exist):
- [ ] REDIS_URL
- [ ] SUPABASE_URL
- [ ] SUPABASE_KEY
- [ ] SUPABASE_DATABASE_URL_POOLER
- [ ] OPENAI_API_KEY
- [ ] OPENROUTER_API_KEY
- [ ] GEMINI_API_KEY
- [ ] SUPREMEAI_JWT_SECRET (64+ bytes)
- [ ] SUPREMEAI_ADMIN_PASSWORD_HASH
- [ ] ENCRYPTION_KEY
- [ ] SUPREMEAI_API_TOKEN
- [ ] STRIPE_API_KEY
- [ ] STRIPE_WEBHOOK_SECRET
- [ ] CI_WEBHOOK_SECRET
- [ ] INFISICAL_TOKEN
- [ ] INFISICAL_CLIENT_SECRET
```

### Render Dashboard - supremeai-admin
```
Required Variables:
- [ ] PORT = 8080
- [ ] ENV = production
- [ ] SERVICE_ROLE = admin
- [ ] ADMIN_CORS_ORIGINS = ["https://supremeai-admin.web.app"]
- [ ] ALLOWED_HOSTS = supremeai-backend-docker.onrender.com
- [ ] MIN_EXPECTED_ROUTES = 5
- [ ] FIREBASE_SERVICE_ACCOUNT_JSON = (sync: false - verify in dashboard)

Critical Secrets (sync: false - verify they exist):
- [ ] REDIS_URL
- [ ] SUPABASE_URL
- [ ] SUPABASE_KEY
- [ ] SUPABASE_DATABASE_URL_POOLER
- [ ] OPENAI_API_KEY
- [ ] OPENROUTER_API_KEY
- [ ] GEMINI_API_KEY
- [ ] SUPREMEAI_JWT_SECRET
- [ ] SUPREMEAI_ADMIN_PASSWORD_HASH
- [ ] ENCRYPTION_KEY
- [ ] SUPREMEAI_API_TOKEN
- [ ] DISCORD_OTP_WEBHOOK_URL
- [ ] RESEND_API_KEY
- [ ] ADMIN_NOTIFICATION_EMAIL
- [ ] INFISICAL_TOKEN
- [ ] INFISICAL_CLIENT_SECRET
```

### Firebase Hosting
```
Firebase Project: supremeai-a
- [ ] firebase.json has rewrites for user target
- [ ] firebase.json has rewrites for admin target
- [ ] Firebase Auth enabled
- [ ] Firestore rules deployed (config/firestore.rules)
- [ ] Hosting targets configured:
  - [ ] user → supremeai.web.app
  - [ ] admin → supremeai-admin.web.app
```

---

## Deployment Steps

### Step 1: Push Code Changes
```bash
# Commit render.yaml changes
git add render.yaml
git commit -m "feat: add FIREBASE_SERVICE_ACCOUNT_JSON to render.yaml (sync: false)"
git push origin main

# Wait for Render auto-deploy to complete (~3-5 minutes)
```

### Step 2: Verify Render Environment Variables
```bash
# Check if FIREBASE_SERVICE_ACCOUNT_JSON exists in Render Dashboard
# If missing, add via Infisical (RECOMMENDED) or manually:
# 1. Go to https://dashboard.render.com
# 2. Select service → Environment tab
# 3. Add FIREBASE_SERVICE_ACCOUNT_JSON
# 4. Click Save → triggers redeploy
```

### Step 3: Deploy Frontend
```bash
# Build and deploy to Firebase
cd apps/studio-client
pnpm run build:user
firebase deploy --only hosting:user

# Build and deploy admin
pnpm run build:admin
firebase deploy --only hosting:admin
```

---

## Smoke Tests (Post-Deployment)

### Backend Health Checks
```bash
# Test 1: User Backend Health
curl -f https://supremeai-backend.onrender.com/health
# Expected: {"status":"healthy"} (HTTP 200)

# Test 2: Admin Backend Health
curl -f https://supremeai-backend-docker.onrender.com/health
# Expected: {"status":"healthy"} (HTTP 200)

# Test 3: Health Check Timeout
curl -f --max-time 10 https://supremeai-backend.onrender.com/health
# Expected: HTTP 200 within 10s (if sleeping, may take 30-60s)
```

### CORS Verification
```bash
# Test 4: CORS Preflight (User Backend)
curl -X OPTIONS https://supremeai-backend.onrender.com/api/v1/health \
  -H "Origin: https://supremeai.web.app" \
  -H "Access-Control-Request-Method: GET" \
  -I
# Expected Headers:
#   HTTP/1.1 200 OK
#   Access-Control-Allow-Origin: https://supremeai.web.app
#   Access-Control-Allow-Credentials: true

# Test 5: CORS Preflight (Admin Backend)
curl -X OPTIONS https://supremeai-backend-docker.onrender.com/api/v1/health \
  -H "Origin: https://supremeai-admin.web.app" \
  -H "Access-Control-Request-Method: GET" \
  -I
# Expected Headers:
#   HTTP/1.1 200 OK
#   Access-Control-Allow-Origin: https://supremeai-admin.web.app
```

### Firebase Rewrite Proxy Test
```bash
# Test 6: Firebase → Backend Proxy (User)
curl -f https://supremeai.web.app/api/v1/health
# Expected: Same as Test 1 (backend response, not 404)

# Test 7: Firebase → Backend Proxy (Admin)
curl -f https://supremeai-admin.web.app/admin-api/health
# Expected: Admin backend response
```

### Authentication Flow Test
```bash
# Test 8: Firebase Login Endpoint Exists
curl -X POST https://supremeai-backend.onrender.com/api/admin/firebase-login \
  -H "Content-Type: application/json" \
  -d '{"idToken":"test"}'
# Expected: 401 or 400 (not 404) - endpoint exists
```

---

## Monitoring Setup

### UptimeRobot Configuration
```
Service 1:
- Name: SupremeAI User Backend
- URL: https://supremeai-backend.onrender.com/health
- Interval: 5 minutes
- Timeout: 30 seconds
- Alert Contacts: [your email]

Service 2:
- Name: SupremeAI Admin Backend
- URL: https://supremeai-backend-docker.onrender.com/health
- Interval: 5 minutes
- Timeout: 30 seconds
- Alert Contacts: [your email]
```

### Verify Alerts Work
```
1. Manually stop supremeai-backend in Render Dashboard
2. Wait for UptimeRobot to detect (2-3 checks)
3. Verify alert received via email/Slack
4. Restart backend in Render Dashboard
5. Verify UptimeRobot sends recovery alert
```

---

## Security Verification

### Environment Variables
```
- [ ] No hardcoded secrets in render.yaml (all use sync: false)
- [ ] No .env files committed to git (check git log)
- [ ] FIREBASE_SERVICE_ACCOUNT_JSON not in version control
- [ ] INFISICAL_TOKEN configured (for secret sync)
```

### CORS Configuration
```
- [ ] User backend only accepts user origins (no admin origins)
- [ ] Admin backend only accepts admin origins (no user origins)
- [ ] No wildcard (*) in CORS_ORIGINS in production
- [ ] HTTPS enforced (no HTTP fallback)
```

### Authentication
```
- [ ] Firebase Service Account JSON present in production
- [ ] JWT_SECRET is 64+ bytes in production
- [ ] Admin password hash configured
- [ ] Token expiry set correctly (SECURITY_CONTEXT_TTL)
```

---

## Performance Baselines

### Expected Metrics
```
Cold Start (after 15min sleep):
- [ ] Backend wake time: 30-60 seconds
- [ ] First request after wake: 200 OK

Warm Performance:
- [ ] Health check: < 100ms
- [ ] API response (p95): < 500ms
- [ ] Database query: < 200ms
- [ ] Redis cache hit: < 50ms

Resource Usage:
- [ ] Memory: < 512MB (free tier limit)
- [ ] CPU: < 100% sustained
- [ ] Database connections: < 10 (pool size)
```

---

## Rollback Plan

### If Deployment Fails

**Backend Issues:**
```bash
# Rollback to previous git commit
git revert HEAD
git push origin main

# Manual restart in Render Dashboard
# Click "Restart" button
```

**Frontend Issues:**
```bash
# Rollback Firebase Hosting
firebase hosting:rollback

# Or redeploy previous build
firebase deploy --only hosting
```

**Database Issues:**
```bash
# Check Supabase dashboard for connection pool
# Verify DATABASE_URL is correct
# Check Render logs for connection errors
```

---

## Post-Deployment Monitoring (Week 1)

### Daily Checks
```
- [ ] Day 1: Verify all health checks passing
- [ ] Day 2: Check UptimeRobot alerts working
- [ ] Day 3: Review Render logs for errors
- [ ] Day 4: Check Firebase Hosting console for errors
- [ ] Day 5: Verify CORS success rate > 99%
- [ ] Day 6: Monitor auth success rate
- [ ] Day 7: Review performance metrics
```

### Weekly Review
```
- [ ] Uptime > 95%
- [ ] Zero critical errors
- [ ] All secrets rotated (if needed)
- [ ] Documentation updated
- [ ] Team notification sent
```

---

## Emergency Contacts

```
SupremeAI Team Lead: [Your Contact]
DevOps: [Your Contact]
On-Call: [Your Contact]

Render Support: https://render.com/support
Firebase Support: https://firebase.google.com/support
Infisical Support: https://infisical.com/support
```

---

## Sign-Off

```
Deployed By: _______________
Date: _______________
Time: _______________
Version: _______________

Verified By: _______________
Date: _______________
Status: [ ] Success [ ] Failed [ ] Rolled Back

Notes:
_________________________________
_________________________________
_________________________________
```

---

**Next Review:** 18 August 2026 (1 week post-deployment)

**Maintained By:** SupremeAI DevOps Team