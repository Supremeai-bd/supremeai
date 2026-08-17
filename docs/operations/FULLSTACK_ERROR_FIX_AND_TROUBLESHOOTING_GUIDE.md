# SupremeAI 2.0 — Fullstack Error Fix & Troubleshooting Guide

> **Project:** SupremeAI 2.0  
> **Target Architecture:** FastAPI Backend (Render) + React/Vite Admin Portal (`supremeai-admin.web.app`) + Flutter Mobile + VS Code Extension  
> **Status:** ACTIVE & PRODUCTION READY  
> **Last Updated:** 2026-07-23  

---

## 📌 Executive Overview (বিবরণ)

এই মাস্টার ট্রাবলশুটিং গাইডে SupremeAI 2.0 প্রজেক্টের ব্যাকএন্ড (FastAPI, Pydantic, Infisical, Render) এবং ফ্রন্টএন্ড (Firebase Hosting, Admin Portal, React/Vite)-এ পূর্বে উদ্ভূত সমস্ত এরর, তাদের টেকনিক্যাল রুট-কজ (Root Cause), এবং এন্টারপ্রাইজ-গ্রেড স্থায়ী সমাধান লিপিবদ্ধ করা হয়েছে।

---

## 🛡️ Part 1: Backend Critical Error Patterns & Solutions

### 🚨 B-01: Pydantic Validation & Cloud Vault Startup Race Condition
- **Symptom (লক্ষণ):** Render ডিপ্লয়মেন্টে কন্টেইনার ক্র্যাশ হওয়া বা হেলথ চেক সংযোগ টাইমআউট খাওয়া (`HTTP 500` / Connection Timeout)।
- **Root Cause (রুট কজ):** `backend/core/config.py`-তে সিক্রেটসমূহ Pydantic-এর static `Field(validation_alias=...)` হিসেবে সংজ্ঞায়িত ছিল। Pydantic স্টার্টআপ টাইমে Infisical ভল্ট পড়ার আগেই OS environment থেকে মান খুঁজতে না পেয়ে `ValidationError` ছুড়ছিল।
- **Implemented Fix (সমাধান):** সিক্রেটসমূহকে Infisical-backed lazy `@property` মেথডে রূপান্তরিত করা হয়েছে:
  ```python
  @property
  def supremeai_admin_password_hash(self) -> str | None:
      val = self._get_cached_secret("SUPREMEAI_ADMIN_PASSWORD_HASH")
      if not val and "pytest" not in sys.modules and os.getenv("CI") != "true":
          raise ValueError("supremeai_admin_password_hash must be explicitly set.")
      return val
  ```

---

### 🚨 B-02: CORS Preflight (HTTP OPTIONS) & Trusted Origin Block
- **Symptom (লক্ষণ):** `https://supremeai-admin.web.app` থেকে ব্যাকএন্ড এপিআই রিড করার সময় ব্রাউজার কন্সোলে `403 Forbidden` অথবা `Cross-Origin Request Blocked` ডিসপ্লে করা।
- **Root Cause (রুট কজ):** ব্রাউজার থেকে যেকোনো ক্রস-অরিজিন রিকোয়েস্ট পাঠানোর আগে একটি প্রাক-রিকোয়েস্ট (HTTP `OPTIONS` Preflight) পাঠানো হয়। `origin_validator.py`-তে `OPTIONS` হ্যান্ডলার এবং `https://supremeai-admin.web.app`-এর জন্য অটো-রেসপন্স হেডার অনুপস্থিত ছিল।
- **Implemented Fix (সমাধান):** `backend/core/security/origin_validator.py`-তে Preflight `OPTIONS` ইন্টারসেপ্টর ও ফলব্যাক ট্রাস্টেড অরিজিন যুক্ত করা হয়েছে:
  ```python
  if request.method == "OPTIONS":
      if not origin or origin in allowed:
          headers = {
              "Access-Control-Allow-Origin": origin or "*",
              "Access-Control-Allow-Credentials": "true",
              "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
              "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-API-Key, Accept, Origin",
          }
          return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"}, headers=headers)
  ```

---

### 🚨 B-03: Render Multi-Account API 404 Service Discovery Failure
- **Symptom (লক্ষণ):** GitHub Actions CI-তে Render API কল করে ডেপ্লয় ট্রিগার করতে গেলে `HTTP 404 Not Found` রিটার্ন করা।
- **Root Cause (রুট কজ):** `RENDER_API_KEY` যে Render টিমের অধীনে তৈরি, সেই টিমে কাঙ্ক্ষিত সার্ভিস আইডিটি (যেমন: `srv-d9fg48bh523c73f63bb0`) না থাকা।
- **Implemented Fix (সমাধান):** `.github/scripts/verify-render-deploy.py` এবং `supreme-core-ci.yml`-এ অটো-ডিসকভারি ও ফলব্যাক লজিক বসানো হয়েছে। ৪০৪ পেলে এটি স্বয়ংক্রিয়ভাবে সক্রিয় সার্ভিস `srv-d9d3n58js32c738n79k0`-তে রি-ম্যাপ করে ডেপ্লয় ও ভেরিফাই সম্পন্ন করে।

---

### 🚨 B-04: CI Polling Sequential Timing & False Positive Timeout
- **Symptom (লক্ষণ):** ব্যাকএন্ড বাস্তবে `LIVE` ও `200 OK` থাকা সত্ত্বেও CI স্ক্রিপ্ট ফেল দেখাচ্ছিল: `No new deploy record found within 3 minutes`.
- **Root Cause (রুট কজ):** রেন্ডারের ফ্রি-টিয়ারে কন্টেইনার বিল্ড হতে ৪ মিনিটের বেশি সময় লাগায় Primary সার্ভিস চেক করতেই ৩ মিনিটের টাইমার শেষ হয়ে যেতো।
- **Implemented Fix (সমাধান):** `verify-render-deploy.py`-তে সার্ভিস ইতিমধ্যে `LIVE` স্ট্যাটাসে থাকলে বয়সের টাইমার স্কিপ করে সরাসরি হেলথ চেক করার লজিক দেওয়া হয়েছে এবং সময়সীমা বাড়িয়ে ১০ মিনিট করা হয়েছে।

---

### 🚨 B-05: CI False-Positive Pass — Admin Backend Never Actually Deployed ⚠️ NEW
- **Symptom:** CI shows `Admin Backend: SUCCESS / HEALTHY` but Render Dashboard shows `supremeai-admin` last deploy was **before** the CI run. New code never reached admin backend.
- **Root Cause (রুট কজ):** তিনটি চেইনড বাগ একসাথে কাজ করছিল:
  1. `verify-render-deploy.py`-তে 404 হলে admin service-কে primary service-এ remap করে health check করছিল।
  2. Admin URL fail হলে `supremeai-backend.onrender.com`-এর health নিয়ে success দেখাচ্ছিল।
  3. `supreme-core-ci.yml`-এ 404 হলে admin deploy-ও primary service-এ ট্রিগার করছিল।
- **CI Log প্রমাণ (Commit `782064b882`):**
  ```
  🗺️ Mapped service target for Admin Backend (Backup)
     -> Active Service ID 'srv-d9d3n58js32c738n79k0' (supremeai-backend)
  ```
- **Implemented Fix (Commit `5412e0226a`):**
  - `verify-render-deploy.py`: 404 হলে remap নিষিদ্ধ — শুধু নির্দিষ্ট service URL-এ health check।
  - `supreme-core-ci.yml`: 404 হলে `exit 1` ও স্পষ্ট error message।
  - `RENDER_DEPLOY_HOOK_URL_BACKUP` GitHub Secret-এ Render Deploy Hook URL সেট করা হয়েছে।

---

### 🚨 B-06: Firebase Hosting Missing Proxy Rewrites for Admin API Paths
- **Symptom:** `supremeai-admin.web.app` থেকে `/admin-api/metrics` বা `/api/v1/health` ফেচ করলে `404 Not Found`।
- **Root Cause:** `firebase.json`-এ শুধু `/api/**` rewrite ছিল, `/admin-api/**` এবং `/api/v1/**` পাথের জন্য proxy rule ছিল না।
- **Implemented Fix:**
  ```json
  { "source": "/admin-api/**", "destination": "https://supremeai-admin.onrender.com/admin-api/**" },
  { "source": "/api/v1/**",    "destination": "https://supremeai-admin.onrender.com/api/v1/**" }
  ```
  `admin/dashboard_light/script.js`-এ `API_BASE` ডায়নামিক করা হয়েছে যাতে `web.app`-এ `''` ব্যবহার হয়।

---

## 🎨 Part 2: Frontend Critical Error Patterns & Solutions

### 🚨 F-01: Admin Portal Backend API Host Disconnection
- **Symptom (লক্ষণ):** `https://supremeai-admin.web.app`-এ প্রবেশ করলে `Failed to fetch backend metrics` অথবা `NetworkError` প্রদর্শিত হওয়া।
- **Root Cause (রুট কজ):** ফ্রন্টএন্ড ক্লায়েন্টে এনভায়রনমেন্ট ভেরিয়েবল `VITE_BACKEND_URL` মিসিং থাকা বা ভুল পোর্টে পয়েন্ট করা।
- **Implemented Fix (সমাধান):** ফ্রন্টএন্ডে প্রাইমারি সার্ভিস (`https://supremeai-backend.onrender.com`) এবং ব্যাকআপ সার্ভিস (`https://supremeai-admin.onrender.com`) এর মধ্যে ডায়নামিক এপিআই ফলব্যাক কনফিগার করা হয়েছে।

---

### 🚨 F-02: Multi-Platform Secret Desynchronization
- **Symptom (লক্ষণ):** ফ্রন্টএন্ড বা ক্লাউড সার্ভিসে এনভায়রনমেন্ট চেঞ্জের পর পুরনো সিক্রেট নিয়ে প্রসেস চলা।
- **Implemented Fix (সমাধান):** সেন্ট্রালাইজড সিঙ্ক্রোনাইজার রান করা:
  ```bash
  python scripts/sync_all_platforms_env.py --apply
  ```
  এটি লোকাল `.env` থেকে GitHub Actions, Render, এবং Vercel-এ রিয়েল-টাইমে ৮৪+ সিক্রেট সিঙ্ক ও মার্জ করে।

---

## 📋 Part 3: Operational Command Handbook (কমান্ড হ্যান্ডবুক)

### 1. Local Health Verification Check
```bash
python .github/scripts/verify-render-deploy.py
```

### 2. Multi-Platform Secret Sync (Apply Changes)
```bash
python scripts/sync_all_platforms_env.py --apply
```

### 3. Manual Admin Backend Deploy via Webhook
```bash
curl -X POST "https://api.render.com/deploy/srv-d9fg48bh523c73f63bb0?key=woFdSrErY2Y"
```

### 4. API Health Endpoints Direct Ping
- **Primary Backend:** `https://supremeai-backend.onrender.com/api/v1/health`
- **Admin Backend:** `https://supremeai-admin.onrender.com/api/v1/health`
- **Admin Portal UI:** `https://supremeai-admin.web.app`

---

*SupremeAI 2.0 — Production Architecture & Engineering Guide*  
*Last Updated: 2026-07-23 | Commits: `782064b8`, `5412e022`, `f209ffde`*
