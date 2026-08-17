# SupremeAI - Immediate Action Plan

**তারিখ:** 11 August 2026  
**বৈচ্ছ三农:** যাচাইকরণের পরaddle স onwards পরিকল্পনা

---

##🎯 Top 3 Immediate Actions (Today/Tomorrow)

### 1. Backend Sleep Prevention (CRITICAL)

**Problem:** Render free tier sleeps after 15 minutes → 30-60s cold start

**Solutions (choose one):**

**Option A: Deploy Existing Cloudflare Worker (RECOMMENDED & FREE)**
```bash
1. Go to the `cloudflare-worker/` directory in this project.
2. The worker is already configured (`wrangler.toml`) to ping backends every 3 minutes.
3. Run `npm install` and deploy it to Cloudflare: `npx wrangler deploy`
4. This is better than UptimeRobot as it includes custom retry logic and exponential backoff designed specifically for Render's cold-start delays.
```

**Option B: Render Paid Plan ($7/month per service)**
- Upgrade both `supremeai-backend` and `supremeai-admin`
- Eliminates sleep completely
- Includes 512MB → 1GB RAM upgrade

**Option C: Vercel/Netlify Backend**
- Migrate backend to Vercel Serverless Functions
- Always-on, no sleep
- Requires code changes (FastAPI → Vercel handler)

**✅ RECOMMENDATION:** Start with Option A (Deploy Existing Cloudflare Worker) - it's completely built-in, free, and specifically optimized for Render's cold starts.

---

### 2. Verify Firebase Service Account in Production

**Steps:**
```bash
1. Go to https://dashboard.render.com
2. Select service: supremeai-backend
3. Click "Environment" tab
4. Check if FIREBASE_SERVICE_ACCOUNT_JSON exists:
   - If YES: ✅ No action needed
   - If NO: Add via Infisical (RECOMMENDED) or Render Dashboard:
     - **Option A (Best):** Add to Infisical vault → auto-syncs to Render
     - **Option B:** Manually add in Render Dashboard → Environment
     - Click "Save" → triggers redeploy
```

**Repeat for:** `supremeai-admin` service

**Why this matters:** Login will fail if this is missing.

**🔐 Security Best Practice:**
- Your project uses **Infisical** for secret management (see `INFISICAL_TOKEN` in .env)
- Store `FIREBASE_SERVICE_ACCOUNT_JSON` in Infisical vault
- Connect Infisical to Render via integration
- Never hardcode secrets in `render.yaml` or version control

---

### 3. Test Live Deployment

**Quick Smoke Tests:**

```bash
# Test 1: Backend Health
curl https://supremeai-backend.onrender.com/health
# Expected: {"status":"healthy"}

# Test 2: CORS Preflight
curl -X OPTIONS https://supremeai-backend.onrender.com/api/v1/health \
  -H "Origin: https://supremeai.web.app" \
  -H "Access-Control-Request-Method: GET"
# Expected: 200 with CORS headers

# Test 3: Firebase Rewrite Proxy
curl https://supremeai.web.app/api/v1/health
# Expected: Same as Test 1 (not 404)

# Test 4: Admin Backend
curl https://supremeai-admin.onrender.com/health
# Expected: {"status":"healthy"}
```

**Browser Tests:**
1. Open https://supremeai.web.app
2. Open DevTools → Network tab
3. Try to login
4. Check for failed requests (red entries)

---

##📅 This Week's Tasks

### Day 1-2: Monitoring Setup
- [x] Deploy the existing Cloudflare Worker (`npx wrangler deploy` inside `cloudflare-worker/`)
- [ ] Verify Cloudflare Worker logs to ensure it's successfully pinging the endpoints
- [ ] Test the worker schedule (runs every 3 mins via cron)

### Day 3-4: Security Audit
- [ ] Verify no hardcoded secrets in client-side code
- [ ] Check CORS headers in production responses
- [ ] Test rate limiting (if enabled)
- [ ] Verify HTTPS only (no HTTP fallback)

### Day 5: Performance Testing
- [ ] Measure cold start time (with sleep)
- [ ] Measure warm response time
- [ ] Check database connection pool
- [ ] Verify Redis caching works

---

##🔧 Configuration Fixes Needed

### 0. Use Infisical for Secret Management (RECOMMENDED)

**Why Infisical?**
- Your project already has `INFISICAL_TOKEN` configured in `.env`
- Centralized secret management across all environments
- Auto-sync to Render, Vercel, Firebase
- Audit logs, rotation, and access control

**Steps:**
```bash
1. Go to https://app.infisical.com
2. Navigate to your project: supremeai-a
3. Add secret: FIREBASE_SERVICE_ACCOUNT_JSON
   - Paste the JSON from .env line 114
   - Mark as production secret
4. Integrate with Render:
   - Settings → Integrations → Render
   - Select services: supremeai-backend, supremeai-admin
   - Map FIREBASE_SERVICE_ACCOUNT_JSON to both services
5. Remove manual env var from Render Dashboard (if exists)
```

**Benefits:**
- ✅ No hardcoded secrets in version control
- ✅ Auto-rotation and versioning
- ✅ Single source of truth for all secrets
- ✅ Team access control

---

### 1. Add FIREBASE_SERVICE_ACCOUNT_JSON to render.yaml

**File:** `render.yaml`

**Add to BOTH services (supremeai-backend AND supremeai-admin):**
```yaml
- key: FIREBASE_SERVICE_ACCOUNT_JSON
  sync: false
```

**⚠️ SECURITY NOTE:** 
- ❌ Never hardcode secret values in `render.yaml` or any version-controlled file
- ✅ Use `sync: false` to inject from Render Dashboard → Environment tab
- ✅ Better: Use **Infisical** (already configured in your project) to auto-inject secrets
- ✅ Best practice: Store in Infisical vault, reference via Render integration

**Why:** Ensures Firebase auth works even if .env sync fails.

---

### 2. Add Timeout Configuration

**File:** `backend/core/config.py` (optional improvement)

```python
# Add this field to Settings class:
STARTUP_TIMEOUT_SECONDS: int = Field(
    default=300,  # 5 minutes
    validation_alias="STARTUP_TIMEOUT_SECONDS"
)
```

**Why:** Prevents premature timeout during cold starts.

---

##🚨 What to Watch Out For

### Common Issues After Deployment

1. **Database Connection Errors**
   - Symptom: 500 errors on API calls
   - Check: Render logs for "connection pool exhausted"
   - Fix: Reduce `UVICORN_WORKERS` to 1 (free tier memory limit)

2. **Redis Connection Timeouts**
   - Symptom: Slower responses, cache misses
   - Check: Upstash dashboard for connection count
   - Fix: Enable connection pooling

3. **CORS Errors in Production**
   - Symptom: Browser console shows CORS errors
   - Check: Response headers for `Access-Control-Allow-Origin`
   - Fix: Verify `USER_CORS_ORIGINS` includes Firebase domain

4. **Auth Token Expiry**
   - Symptom: Users get logged out after 1 hour
   - Check: `SECURITY_CONTEXT_TTL` in config
   - Fix: Adjust TTL or implement token refresh

---

##📊 Success Metrics

**Week 1 Goals:**
- ✅ Uptime > 95% (excluding planned sleep)
- ✅ API response time < 500ms (p95)
- ✅ CORS success rate > 99%
- ✅ Auth success rate > 99%

**Month 1 Goals:**
- ✅ Uptime > 99.5% (with sleep prevention)
- ✅ Zero CORS errors in production
- ✅ All health checks passing
- ✅ < 2s cold start time

---

##🆘 Emergency Contacts

**If Backend Goes Down:**
1. Check Render dashboard: https://dashboard.render.com
2. Check logs: `render logs -s supremeai-backend`
3. Manual restart: Click "Restart" in Render dashboard
4. Check Cloudflare Worker logs for ping failures

**If Frontend Broken:**
1. Check Firebase Hosting: https://console.firebase.google.com
2. Check browser console for errors
3. Verify `firebase.json` hasn't changed
4. Rollback if needed: `firebase hosting:rollback`

---

##📝 Quick Reference Commands

```bash
# Local Development
cd backend && poetry run uvicorn main:app --reload --port 8080
cd apps/studio-client && pnpm dev

# Deploy Backend (Render auto-deploys on git push)
git push origin main

# Deploy Frontend (Firebase)
firebase deploy --only hosting

# Check Logs
render logs -s supremeai-backend --tail

# Test Locally
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/health
```

---

**Next Review:** Schedule for 18 August 2026 (1 week from now)

**Owner:** SupremeAI Team  
**Priority:** P0 (Critical) - Backend sleep prevention