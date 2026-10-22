# Webhook Primary & Root-Level Permanent Fix — প্রয়োজনীয়তা ও পরিকল্পনা (বাংলা)

> তারিখ: 2026-10-21
> রিপোজিটরি: supremeai-open
> উদ্দেশ্য: Guest chat-এ webhook (stealth web relay) প্রাইমারি হবে এবং webhook রুট-লেভেল থেকে স্থায়ীভাবে ঠিক হবে।

---

## ১. প্রয়োজনীয়তা (Requirement)

1. Guest chat-এ **webhook (stealth web relay) প্রাইমারি** provider হবে — API fallback নয়।
2. Webhook সমস্যা হলেও **root-level থেকে স্থায়ী সমাধান** করা হবে (patch/hack নয়)।
3. Webhook fail করলে honest failover → API provider (zero silent fallback)।
4. Webhook health/config যাচাই করা হবে startup-এ।
5. Guest chat কখনো "only API reply" দেখাবে না যতক্ষণ webhook সক্ষম।

---

## ২. বর্তমান অবস্থা (Current State)

- routing_policy.json: web provider প্রথমে (primary) রাখা হয়েছে।
- gateway/provider_chain.py: web relay URL না থাকলে দ্রুত fail (RuntimeError) → failover।
- stealth_webhook.py (stdlib asyncio) লোকাল mock-এ 200 OK (implementation OK)।
- Deployed backend (supremeai-api) stealth_priority1_configured=true কিন্তু guest chat API model দেখায় → relay service কাজ করছে না (403/timeout)।
- .env-এ SUPREMEAI_WEB_RELAY_URL নেই; SUPREMEAI_CF_WORKER_URL একটি browser-scraper, chat relay নয়।

---

## ৩. মূল কারণ (Root Cause)

1. **Web relay service URL ভুল/অনুপস্থিত:** SUPREMEAI_WEB_RELAY_URL সেট নেই; CF worker chat endpoint নয় → 403।
2. **Relay service down/misconfigured:** deployed stealth relay 403 ফেরত দেয়, তাই API fallback।
3. **Gateway fallback to CF worker:** অপ্রয়োজনীয় 403 delay; এখন সরানো হয়েছে (fast fail)।
4. **Root-level ফিক্স নেই:** relay health/config/startup validation নেই।

---

## ৪. স্থায়ী সমাধান (Permanent Fix Plan)

### A. Config/Env (Root)
- `.env` / Render env-এ `SUPREMEAI_WEB_RELAY_URL` যোগ করুন → প্রকৃত chat-capable relay endpoint।
- `SUPREMEAI_STEALTH_WEBHOOK_SECRET` যোগ করুন (যদি relay সিক্রেট চায়)।
- CF worker (browser-scraper) কে chat relay হিসেবে ব্যবহার করবেন না।

### B. Gateway Code (Root)
- `stealth_webhook.py`: retry (1x) + honest logging + fast-fail on 401/403/404।
- `provider_chain.py`: web provider primary; failover on transport/auth errors।
- `main.py`/`create_app`: startup health probe for relay (optional, fail-open)।
- routing_policy.json: web first, then API providers。

### C. Relay Service (Root)
- Ghost tower / browser relay service-এ `/v1/chat/completions` endpoint নিশ্চিত করুন।
- Stealth secret validation ঠিক করুন (403 এড়াতে)。
- Relay health endpoint `/health` যোগ করুন。

### D. Verification
- Local mock relay test (200 OK) — সম্পন্ন।
- Gateway boot with web primary (fast fail if no URL) — সম্পন্ন।
- Full test suite — ৮৯৯ passed, ruff clean。

---

## ৫. বাস্তবায়ন অবস্থা (Implementation Status)

- [x] routing_policy.json: web primary।
- [x] provider_chain.py: web fast-fail (no CF fallback)।
- [x] stealth_webhook.py: local mock 200 OK (implementation OK)。
- [ ] SUPREMEAI_WEB_RELAY_URL env সেট (deployment)。
- [ ] Relay service /v1/chat/completions + health endpoint verify。
- [ ] Stealth secret configured。

---

## ৬. পরবর্তী পদক্ষেপ

1. Deployed relay service ঠিক করুন (ghost tower) — /v1/chat/completions + health。
2. Render env-এ SUPREMEAI_WEB_RELAY_URL সেট করুন。
3. Gateway redeploy করুন。
4. Guest chat verify করুন (webhook reply, not API-only)。

---

*এই ডকুমেন্ট user requirement অনুযায়ী তৈরি; root-level fix plan অন্তর্ভুক্ত।*
