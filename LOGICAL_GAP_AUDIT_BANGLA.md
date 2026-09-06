# লজিক্যাল গ্যাপ অডিট রিপোর্ট (Bengali)
## SupremeAI কোডবেস তদনির্ধারিত লজিক্যাল ফাঁপ (Logical Gap Audit Report)

**রিপোর্ট তারিখ:** ২০২৬ সেপ্টেম্বর ০৭  
**রিপোর্টার:** Kilo অডিট এজেন্ট  
**রিপোজিটরি:** F:\supremeai  
**মোট আইডেন্টিফাইয়ার সংখ্যা:** ১৭টি  
**আইডিয়ান করা ফাইল সংখ্যা:** ৯টি  

---

## ১. কার্যকরী সংক্ষেপ (Executive Summary)

এই রিপোর্টটি SupremeAI কোডবেসএর সম্পূর্ণ তদনির্ধারিত অডিটের ফলাফল উপস্থাপন করে, যাতে গিট ট্র্যাকিং স্থিতি, লজিক্যাল ফাঁপ (logical gaps), নিরাপত্তা দুর্বলতা এবং স্ট্রাকচারাল সমস্যাগুলো বিশ্লেষণ করা হয়েছে। মোট ১৭টি তীব্রতা (severity) এবং মূল কারণ সহ চিহ্নিত হয়েছে। এর মধ্যে **ক্রিটিক্যাল** ৪টি, **হাই** ৪টি, **মিডিয়াম** ৩টি, **লো** ১টি এবং অপরিবর্তনীয় স্ট্রাকচারাল ৬টি রয়েছে।

### মূল উদ্ভাবনী পয়েন্টগুলো:

- **SSRF প্রটেকশন একটি ইম্পোর্ট পাথ বাগে ভরে আছে** যা সবসময় ImportError ঘটিয়ে দেয়, ফলে ত্রৈমাসিক ওয়েটারফল স্ক্রিপ্টের পরিবর্তে দুর্বল ইনলাইন চেকে ফলব্যাক করে।
- **সর্বোচ্চ ৪টি হ্যার্ডকোডেড সিক্রেট** গিটের মধ্যে সংরক্ষিত ফাইলগুলোতে রয়েছে, যা গিটলিকস অ্যালোয়ালিস্টের মাধ্যমে বাছাই পাড়ি যায়।
- **Supabase বুটস্ট্র্যাপ স্কিমা** `render_account_states` এবং `render_preflight_events` টেবিল অন্তর্ভুক্ত করে না, যা অ্যাপ্লিকেশন কোড থেকে সরাসরি রেফারেন্স করা হয়।
- **ব্রাউজার রুটগুলোতে একাধিক অ-প্রামাণিক এন্ডপয়িন্ট** রয়েছে যা সরাসরি অথেনটিকেশন ছাড়াই কাজ করে।

---

## ২. গিট ট্র্যাকিং স্থিতি (Git Tracking Status) — [✅ হালনাগাদ: সব ফাইল ট্র্যাকড]

### ২.১ ওপেন-ট্যাব ফাইলগুলোর ট্র্যাকিং (Open-Tab Files)

| # | ফাইল পাথ | ট্র্যাক করা? | বর্তমান স্থিতি |
|---|-----------|:---:|-----|
| ১ | `backend/database/migrations/20_create_browser_credentials.sql` | ✅ হ্যাঁ | **ট্র্যাক করা হয়েছে** (`git ls-files` দ্বারা যাচাইকৃত) |
| ২–১৫ | (অন্যান্য ১৪টি ওপেন-ট্যাব ফাইল) | ✔️ হ্যাঁ | স্বাভাবিকভাবে ট্র্যাক করা আছে |

**সারসংক্ষেপ:** ১৫টি ওপেন-ট্যাব ফাইলের সবকটিই (১০০%) এখন গিট-ট্র্যাক করা।

### ২.২ অতিরিক্ত অ্যানট্র্যাক্ড ফাইলগুলোর স্থিতি (Additional Files Verification)

অডিটে পূর্বে উল্লেখিত অ্যানট্র্যাক্ড ফাইলগুলোর বর্তমান ট্র্যাকিং অবস্থা:

| # | ফাইল পাথ | বর্তমান ট্র্যাকিং স্থিতি | নোট |
|---|-----------|:---:|-----|
| ১ | `backend/models/render_account_state.py` | ✅ **ট্র্যাক করা** | গিটে কমিট ও ট্র্যাকড |
| ২ | `backend/services/render_account_service.py` | ✅ **ট্র্যাক করা** | গিটে কমিট ও ট্র্যাকড |
| ৩ | `backend/api/routes/render_preflight_admin.py` | ✅ **ট্র্যাক করা** | গিটে কমিট ও ট্র্যাকড |
| ৪ | `backend/alembic_migrations/versions/2026_09_06_120000_add_render_account_state.py` | ✅ **ট্র্যাক করা** | গিটে কমিট ও ট্র্যাকড |

### ২.৩ অন্যান্য ফাইলগুলোর ট্র্যাকিং স্থিতি (Verified Tracked Files)

| ফাইল পাথ | বর্তমান ট্র্যাকিং স্থিতি |
|----------|:---:|
| `backend/tests/test_render_account_service.py` | ✅ **ট্র্যাক করা** |
| `frontend/src/components/admin/RenderPreflightWidget.tsx` | ✅ **ট্র্যাক করা** |
| `frontend/src/utils/secureWebSocket.ts` | ✅ **ট্র্যাক করা** |
| `scripts/ci/render_recheck_scheduler.py` | ✅ **ট্র্যাক করা** |
| `scripts/generate_script_index.py` | ✅ **ট্র্যাক করা** |

> **যাচাই ফলাফল:** সেকশন ২-এ চিহ্নিত সব কয়টি ফাইলই বর্তমানে গিটে সফলভাবে ট্র্যাকড রয়েছে। কোনো অ্যানট্র্যাক্ড ফাইল অবশিষ্ট নেই।

---

## ৩. অগ্রাধিকার শ্রেণীবিন্যাস (Priority Classification)

| অগ্রাধিকার | তীব্রতা | গ্যাপ সংখ্যা | তালিকা |
|------------|:---:|:---:|-------|
| **P0 — অবিলম্বে প্রয়োজন** | ক্রিটিক্যাল (Critical) | ৪টি | ১, ৭, ১১, ১২ |
| **P1 — ২৪-ঘণ্টার মধ্যে ঠিক করতে হবে** | হাই (High) | ৪টি | ২, ৩, ৬, ১৫ |
| **P2 — ৭ দিনের মধ্যে ঠিক করতে হবে** | মিডিয়াম (Medium) | ৩টি | ৪, ৫, ১৭ |
| **P3 — নর্মাল রোডম্যাপে** | লো (Low) | ১টি | ১৪ |
| **P4 — স্ট্রাকচারাল** | মিডিয়াম/লো | ৩টি | ৮, ৯, ১০, ১৩, ১৬ |

> **মন্তব্য:** গ্যাপ ৮, ৯, ১০ এবং ১৩ মিডিয়াম সেভত্বে বরাদ্দ করা হয়েছে কিন্তু স্ট্রাকচারাল প্রকৃতির জন্য P4 বিভাগে স্থান পায়। গ্যাপ ১৬ (/extract SSRF bypass) তীব্রতা হাই হয় তবে এটি P1-এ স্থান পায়।

### ৩.১ লাইভ কোডবেস ভেরিফিকেশন স্থিতি ম্যাট্রিক্স (Live Status Verification Matrix)

২০২৬ সেপ্টেম্বর ০৭ তারিখে কোডবেস ট্রাভার্স করে প্রাপ্ত ১৭টি গ্যাপের হালনাগাদ স্থিতি:

| গ্যাপ # | শিরোনাম | পূর্বের তীব্রতা | বর্তমান স্থিতি (Status) | বর্তমান বাস্তবতা ও প্রভাব |
|:---:|---|:---:|:---:|---|
| **১** | SSRF ইম্পোর্ট পাথ বাগ | 🔴 ক্রিটিক্যাল | 🔴 **বিদ্যমান (Active)** | `core/security/__init__.py:437`-এ `from core.security.ssrf_protection` রয়েছে, কিন্তু ফাইলটি `protection/ssrf_protection.py`-এ। ইনলাইন ফলব্যাকে চলছে। |
| **২** | PERMISSION_REQUESTS ডেড কোড | 🟠 হাই | 🔴 **বিদ্যমান (Active)** | `browser.py:132`-এ লিস্ট ডিফাইন করা আছে, কিন্তু সিস্টেমে কোনো কোড এতে রিকোয়েস্ট পুশ করে না। |
| **৩** | `/surf/skip-auth` ওপেন এন্ডপয়েন্ট | 🟠 হাই | 🔴 **বিদ্যমান (Active)** | `browser.py:528`-এ কোনো Auth Dependency নেই; যে কেউ কল করতে পারে। |
| **৪** | `hash()` নন-ডিটারমিনিজম | 🟡 মিডিয়াম | 🔴 **বিদ্যমান (Active)** | `browser.py:783`-এ `sess_{hash(body.get('url'))}` এখনো ব্যবহার হচ্ছে। |
| **৫** | URL পারমিশন / টাস্ক আইডি কলিশন | 🟡 মিডিয়াম | 🔴 **বিদ্যমান (Active)** | `browser.py:562, 571, 632`-এ `len() + 1` প্যাটার্ন বিদ্যমান। |
| **৬** | Supabase বুটস্ট্র্যাপ স্কিমা গ্যাপ | 🟠 হাই | 🔴 **বিদ্যমান (Active)** | `supabase_client.py:760`-এর `get_bootstrap_statements()`-এ `render_account_states` ও `render_preflight_events` DDL নেই (শুধুমাত্র Alembic-এ আছে)। |
| **৭** | Infisical Credentials হার্ডকোডেড | 🔴 ক্রিটিক্যাল | 🔴 **বিদ্যমান (Active)** | ৪টি ডেভপস/ডিপ্লয় স্ক্রিপ্টে ডিফল্ট ভ্যালু হিসেবে Client ID ও Project ID হার্ডকোডেড। |
| **৮** | Render সার্ভিস আইডি হার্ডকোডেড | 🟡 মিডিয়াম | 🔴 **বিদ্যমান (Active)** | `update_infisical_render.py` ও `update_vault.py`-এ `srv-da666f8u01pc739bm3t0` সরাসরি সেট করা। |
| **৯** | হার্ডকোডেড অ্যাডমিন ইমেল ও প্লেসহোল্ডার কী | 🟡 মিডিয়াম | 🔴 **বিদ্যমান (Active)** | `add_secrets_to_infisical.py`-এ ইমেল ও `YOUR_OPENAI_API_KEY` বিদ্যমান। |
| **১০** | টেস্ট স্ক্রিপ্টে সিক্রেট মান প্রিন্ট | 🟡 মিডিয়াম | 🔴 **বিদ্যমান (Active)** | `test_infisical.py:38, 52`-এ `secret.secret_value` প্রিন্ট হচ্ছে। |
| **১১** | ফলব্যাক এনক্রিপশন কী হার্ডকোডেড | 🔴 ক্রিটিক্যাল | 🔴 **বিদ্যমান (Active)** | `upload_infisical.py:52`-এ `supremeai-default-fallback-encryption-key-2026-v2` সরাসরি সেট করা। |
| **১২** | Gitleaks অ্যালোয়ালিস্ট জেনেরিক রেগেক্স | 🔴 ক্রিটিক্যাল | 🔴 **বিদ্যমান (Active)** | `.gitleaks.toml`-এ `sk-...`, `rnd_...`, `eyJ...` গ্লোবালি বাইপাস করছে। |
| **১৩** | পুরনো CI স্ক্রিপ্ট রেফারেন্স | 🟡 মিডিয়াম | ⚠️ **আংশিক অমীমাংসিত** | `cost_guard_monitor.py` echo দিয়ে বাইপাস করা আছে; তবে `render_cooldown_recheck` স্টেপ রুটের `scripts/ci/` থেকে রান হয়। |
| **১৪** | ভুল টাইপ অ্যানোটেশন | 🟢 লো | 🔴 **বিদ্যমান (Active)** | `backend/worker_service.py:161`-এ `result: Callable[..., Any]` টাইপিং রয়েছে (Coroutine এর বদলে)। |
| **১৫** | ডিক্রিপশন `key_ref` লজিক বাগ | 🟠 হাই | 🔴 **বিদ্যমান (Active)** | `secure_credential_store.py:125`-এ `if ... or key_ref:` থাকলে ডিক্রিপশন সরাসরি বাইপাস হয়ে সাইফারটেক্সট ফেরত যায়। |
| **১৬** | `/extract` এন্ডপয়েন্টে SSRF বাইপাস | 🟠 হাই | 🔴 **বিদ্যমান (Active)** | `browser.py:995`-এ URL-কে কোনো `is_safe_url()` ভ্যালিডেশন ছাড়াই প্রসেস করা হচ্ছে। |
| **১৭** | প্লেইনটেক্সট সিক্রেট রেসপন্সে রিটার্ন | 🟡 মিডিয়াম | 🔴 **বিদ্যমান (Active)** | `browser.py:436`-এ `/credentials/{id}/use` এন্ডপয়েন্ট ডিক্রিপ্টেড পাসওয়ার্ড/সিক্রেট রেসপন্স বডিতে ফেরত দেয়। |
| **সেকশন ২** | গিট আনট্র্যাকড ফাইল অসামঞ্জস্য | 🔴 সমস্যা | ✅ **সম্পূর্ণ ফিক্সড (Resolved)** | অডিটে উল্লেখিত সব কয়টি ফাইল (৯টি ফাইল) বর্তমানে গিটে সফলভাবে ট্র্যাকড ও কমিটেড। |

---

## ৪. বিশদ গ্যাপ বিশ্লেষণ (Detailed Findings)

---

### গ্যাপ ১: SSRF ইম্পোর্ট পাথ বাগ (SSRF Import Path Bug)

| ক্ষেত্র | মান |
|--------|-----------------|
| **ফাইল** | `backend/core/security/__init__.py` |
| **লাইন** | ৪৩৭ |
| **তীব্রতা** | 🔴 ক্রিটিক্যাল |
| **ধরণ** | নিরাপত্তা / ইম্পোর্ট ব্যবস্থাপনা |

**কোড:**
```python
# backend/core/security/__init__.py:437
try:
    from core.security.ssrf_protection import is_safe_url as _ssrf_check
    return _ssrf_check(url)
except ImportError:
    # Fallback inline check (weak)
    ...
```

**মূল কারণ:** একটি `try/except ImportError` ব্লকে `from core.security.ssrf_protection import is_safe_url` ইম্পোর্ট করা হয়েছে, কিন্তু বাস্তব মডিউলটি `core/security/protection/ssrf_protection.py` এ অবস্থিত। ফলস্বরূপ, `ImportError` সবসময় ঘটে এবং কোডটি কখনোই সেন্ট্রালাইজড SSRF প্রোটেকশন ব্যবহার করে না — এটি সর্বাধিক দুর্বল ইনলাইন চেকে ফলব্যাক করে।

**প্রভাব:** SSRF (Server-Side Request Forgery) আক্রমণ রোধ করতে পারে না। মেটাডেটা আকাশে (169.254.169.254), লুপব্যাক, লিঙ্ক-লোকাল এবং বেস্বয়াস্টিক IP ঠিঠিয়ে আছে না।

**সুপারিশ:**
```python
from core.security.protection.ssrf_protection import is_safe_url as _ssrf_check
```

---

### গ্যাপ ২: PERMISSION_REQUESTS মৃত কোড (PERMISSION_REQUESTS Dead Code)

| ক্ষেত্র | মান |
|--------|-----------------|
| **ফাইল** | `backend/api/routes/browser.py` |
| **লাইন** | ১৩২, ৫৯০–৬০৪ |
| **তীব্রতা** | 🟠 হাই |
| **ধরণ** | ডেড কোড / লজিক্যাল ফাঁপ |

**কোড:**
```python
# browser.py:132
PERMISSION_REQUESTS: list[dict[str, Any]] = []

# browser.py:590-604
@router.get("/urls/requests")
def get_requests():
    return {"requests": PERMISSION_REQUESTS}

@router.post("/urls/requests/{id}/decision", dependencies=[Depends(require_admin_token)])
def decision(request_id: str, req: DecisionRequest):
    for r in PERMISSION_REQUESTS:
        if r["id"] == request_id:
            r["status"] = "APPROVED" if req.approved else "DENIED"
            return {"success": True}
    raise HTTPException(status_code=404, detail="Request not found")
```

**মূল কারণ:** `PERMISSION_REQUESTS` তালিকাটি কখনোই কোনো কোড থেকে পূরণ করা হয় না। কোনো এন্ডপয়িন্ট এই তালিকাটিতে আইটেম যোগ করে না। ফলস্বরূপ `/urls/requests/{id}/decision` সর্বাপেক্ষে ৪০৪ রিটার্ন করে।

**প্রভাব:** অ্যাডমিনরা কখনোই কোনো পারমিশন রিকোয়েস্ট অ্যাপ্রুভ বা ডিএন করতে পারেন না। গেটওয়ে কাজ করে না।

**সুপারিশ:** যখন কোনো URL রিকোয়েস্ট বাধা পায়, তখন `PERMISSION_REQUESTS` তালিকাটিতে আইটেম যোগ করার জন্য একটি এন্ডপয়িন্ট যোগ করুন, অথবা মৃত কোডটি সম্পূর্ণ মুছে ফেলুন।

---

### গ্যাপ ৩: skip_auth এন্ডপয়িন্ট অনপ্রামাণিক (Unauthenticated skip_auth Endpoint)

| ক্ষেত্র | মান |
|--------|-----------------|
| **ফাইল** | `backend/api/routes/browser.py` |
| **�াইন** | ৫২১–৫২৪ |
| **তীব্রতা** | 🟠 হাই |
| **ধরণ** | অথেনটিকেশন ব্যবস্থাপনা / গোপনীয়তা |

**কোড:**
```python
# browser.py:521-524
@router.post("/surf/skip-auth")
def skip_auth(body: dict[str, str]):
    PAUSED_STATE["paused"] = False
    return {"status": "auth_skipped"}
```

**মূল কারণ:** `/surf/skip-auth` এন্ডপয়িন্টে কোনো অথেনটিকেশন ডিপেন্ডেন্সি নেই। এটি শুধমাত্র `PAUSED_STATE["paused"] = False` সেট করে, কিন্তু নামটি বলে যেন "অথেনটিকেশন স্কিপ করা হয়েছে" — যা ব্যবহারকারীদের ভুল ধারণা দেয়।

**প্রভাব:** যে কোনো ব্যক্তি অ্যাপিআই থেকে এই এন্ডপয়িন্টটি কল করে ব্রাউজারের পেজজ অবস্থা পরিবর্তন করতে পারেন।

**সুপারিশ:** `Depends(require_admin_token)` যোগ করুন এবং এন্ডপয়িন্টের আচরণ ও নামটি পরিষ্কার করুন (যেমন `/surf/resume` এর মতো)।

---

### গ্যাপ ৪: hash() অনির্ধারিত প্রবণতা (hash() Non-Determinism)

| ক্ষেত্র | মান |
|--------|-----------------|
| **ফাইল** | `backend/api/routes/browser.py` |
| **লাইন** | ৭৭৬ |
| **তীব্রতা** | 🟡 মিডিয়ান |
| **ধরণ** | ডিটারমিনিস্টিসিটি / নিরাপত্তা |

**কোড:**
```python
# browser.py:776
return {"success": True, "session_id": f"sess_{hash(body.get('url'))}"}
```

**মূল কারণ:** Python-এর বিল্টিন `hash()` ফাংশনটি প্রক্রিয়া-আপেক্ষিকভাবে র‍্যান্ডমাইজ করা হয় (`PYTHONHASHSEED`)। এটি সেশন আইডি জেনারেট করতে ব্যবহার করলে একই URL প্রতিটি প্রক্রিয়া রিস্টার্টের সময় ভিন্ন হয়। এটি ক্রিপ্টোগ্রাফিকভাবে নিরাপদও নয়।

**প্রভাব:** সেশন আইডি ভিদ্যমান নয়, পূর্বাভাসযোগ্য নয় এবং সহজে কলিশন হয়ে পড়তে পারে।

**সুপারিশ:**
```python
import hashlib
session_id = hashlib.sha256(body.get('url', '').encode()).hexdigest()[:16]
```

---

### গ্যাপ ৫: URL পারমিশন/টাস্ক আইডি কলিশন (URL Permission/Task ID Collision)

| ক্ষেত্র | মান |
|--------|-----------------|
| **ফাইল** | `backend/api/routes/browser.py` |
| **लাইन** | ৫৫৫, ৫৬৪, ৫৭৩, ৬২৫ |
| **তীব্রতা** | 🟡 মিডিয়ান |
| **ধরণ** | আইডি জেনারেশন / ডেটা ইন্টিগ্রিটি |

**কোড:**
```python
# browser.py:555
perm["id"] = f"perm_{len(URL_PERMISSIONS) + 1}"

# browser.py:625
task_id = f"task_{len(TASKS) + 1}"
```

**মূল কারণ:** আইডিগুলো `len(list) + 1` ফর্মাটে জেনারেট করা হয়। যখন আইটেমগুলো ডিলিট করা হয়, তখন তালিকার দৈর্ঘ্য কমে যায় এবং পরবর্তীতে যোগ করা আইটেমগুলোর সাথে ডুপ্লিকেট আইডি তৈরি হয়।

**প্রভাব:** আইডি কলিশন হলে, সঠিক আইটেমটি আপডেট বা ডিলিট হয় না — ভুল আইটেম পরিবর্তিত হয়।

**সুপারিশ:** UUID ব্যবহার করুন:
```python
import uuid
perm["id"] = f"perm_{uuid.uuid4().hex[:12]}"
```

---

### গ্যাপ ৬: Supabase বুটস্ট্র্যাপ স্কিমা ফাঁপ (Supabase Bootstrap Schema Gap)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فাইল** | `backend/database/supabase_client.py` |
| **লাইน** | ৭৬০–৭৭৮ (বুটস্ট্র্যাপ), ১৬০৬–১৬৭১ (ব্যবহৃত রেফারেন্স) |
| **তীব্রতা** | 🟠 হাই |
| **ধরণ** | স্কিমা গ্যাপ / ডেটাবেস |

**কোড:**
```python
# supabase_client.py:210-778 — get_bootstrap_statements()
@classmethod
def get_bootstrap_statements(cls) -> list[str]:
    return [
        ...
        "CREATE TABLE IF NOT EXISTS browser_credentials ( ... );",  # 762-774
        ...
    ]  # শেষ: লাইন 778

# supabase_client.py:1606-1671 — টেবিল রেফারেন্স করে তবে বুটস্ট্র্যাপে নেই
def get_render_account_states(self, role: str | None = None) -> list[dict[str, Any]]:
    query = client.table("render_account_states").select("*")  # 1612
    ...

def upsert_render_account_state(self, state_dict: dict[str, Any]) -> dict[str, Any] | None:
    res = client.table("render_account_states").upsert(...)  # 1628
    ...

def record_render_preflight_event(self, event_dict: dict[str, Any]) -> dict[str, Any] | None:
    res = client.table("render_preflight_events").insert(...)  # 1642
    ...

def get_render_preflight_events(self, ...) -> list[dict[str, Any]]:
    query = client.table("render_preflight_events").select(...)  # 1661
```

**মূল কারণ:** `get_bootstrap_statements()` মেথডটি `render_account_states` এবং `render_preflight_events` টেবিল তৈরি করে না। এই টেবিলগুলো শুধমাত্র `backend/alembic_migrations/versions/2026_09_06_120000_add_render_account_state.py` মিগ্রেশন দ্বারা তৈরি করা হয় (যি গিটে ট্র্যাক করা আছে)। যদি শুধমাত্র বুটস্ট্র্যাপ চালিয়ে Supabase সেটআপ করা হয়, তাহলে রানটাইমে `PGError: relation does not exist` ত্রুটি ঘটে।

**প্রভাব:** Supabase-এর বুটস্ট্র্যাপ প্রক্রিয়াজনিত ফাঁপে টেবিল অস্তিত্ব বজায় রাখা হয় না, ফলস্বরূপ রেন্ডার অ্যাকাউন্ট স্টেট এবং প্রিফ্লাইট ইভেন্টগুলি রেন্ডার করতে ব্যরক পারে না।

**সুপারিশ:** `get_bootstrap_statements()` এর তালিকায় `render_account_states` এবং `render_preflight_events` এর DDL যোগ করুন।

---

### গ্যাপ ৭: হ্যার্ডকোডেড Infisical গুপ্ত রহস্য (Hardcoded Infisical Credentials)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فাইল** | `scripts/deploy/update_infisical_render.py:12-14` |
| | `scripts/deploy/add_secrets_to_infisical.py:5-7` |
| | `scripts/devops/update_vault.py:11-13` |
| | `scripts/devops/test_infisical.py:7-9` |
| **তীব্রতা** | 🔴 ক্রিটিক্যাল |
| **ধরণ** | গোপনীয়তা / সিকিউরিটি |

**কোড:**
```python
# update_infisical_render.py:12-14
client_id = os.getenv("INFISICAL_CLIENT_ID", "9f2363cf-3cec-43f6-b155-a8625de19250")
client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
project_id = os.getenv("INFISICAL_PROJECT_ID", "92aa20c4-aef5-4e33-82bd-efb06058aaf0")
```

**মূল কারণ:** `INFISICAL_CLIENT_ID` এবং `INFISICAL_PROJECT_ID` এর মানগুলোকে `os.getenv()`-এর ডিফল্ট ফলাফল হিসেবে হ্যার্ডকোড করা হয়েছে। যদি এই পরিবেশ পরিবর্তীটি খুবি ম্যানেজ করা না হয়, তাহলে গিট রিপোজিটিতে এই গুপ্ত রহস্য সংরক্ষিত থাকে।

**প্রভাব:** Infisical ক্লায়েন্ট আইডি এবং প্রকল্প আইডি গিট ইতিহাসে স্থায়ীভাবে ফাঁস হয় — গিটলিকস অ্যালোয়ালিস্ট পাড�়ি যায়।

**সুপারিশ:**
```python
client_id = os.getenv("INFISICAL_CLIENT_ID")
if not client_id:
    raise RuntimeError("INFISICAL_CLIENT_ID পরিবেশ পরিবর্তী প্রয়োজন")
```

---

### গ্যাপ ৮: হ্যার্ডকোডেড Render সেবা আইডি (Hardcoded Render Service ID)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فাইল** | `scripts/deploy/update_infisical_render.py:26` |
| | `scripts/devops/update_vault.py:30` |
| **তীব্রতা** | 🟡 মিডিয়ান |
| **ধরণ** | কনফিগারেশন হ্যার্ডকোডিং |

**কোড:**
```python
# update_infisical_render.py:26
value = "srv-da666f8u01pc739bm3t0"

# update_vault.py:30
secret_value="srv-da666f8u01pc739bm3t0"
```

**মূল কারণ:** Render সার্ভিস আইডি সরাসরি হ্যার্ডকোড করা হয়েছে। এটি পরিবেশ উপমান থেকে আসা উচিত।

**সুপারিশ:** `os.getenv("RENDER_PRIMARY_SVC_ID")` ব্যবহার করুন।

---

### গ্যাপ ৯: হ্যার্ডকোডেড অ্যাডমিন ইমেল ও প্লেসহোল্ডার কী (Hardcoded Admin Email & Placeholder Key)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فাইল** | `scripts/deploy/add_secrets_to_infisical.py:69-70` |
| **তীব্রতা** | 🟡 মিডিয়ান |
| **ধরণ** | গোপনীয়তা / কনফিগারেশন |

**কোড:**
```python
# add_secrets_to_infisical.py:67-70
secrets_to_add = {
    "ADMIN_EMAIL": "niloyjoy7@gmail.com",
    "OPENAI_API_KEY": "YOUR_OPENAI_API_KEY"
}
```

**মূল কারণ:** অ্যাডমিন ইমেল হ্যার্ডকোডেড এবং `YOUR_OPENAI_API_KEY` প্লেসহোল্ডারটি প্রকৃত API কী হিসেবে গিটে জমা থাকে — যার ফলে সিস্টেমে একটি বাজে সিক্রেট সঞ্চয় করা হয়।

**সুপারিশ:** এই মানগুলো পরিবেশ পরিবর্তী থেকে পড়ুন।

---

### গ্যাপ ১০: টেস্টে সিক্রেট ফাঁস (Secret Exposure in Test)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فাইল** | `scripts/devops/test_infisical.py:38, 52` |
| **তীব্রতা** | 🟡 মিডিয়ান |
| **ধরণ** | সিক্রেট লিকেজ |

**কোড:**
```python
# test_infisical.py:38
print(f"Success! Secret value: {secret.secret_value}")

# test_infisical.py:52
print(f"Success! Secret value: {secret.secret_value}")
```

**মূল কারণ:** গোপন সিক্রেট মানগুলি সরাসরি স্ট্যান্ডার্ট আউটপুটে প্রিন্ট করা হয়।

**প্রভাব:** CI লগ, টার্মিনাল স্ক্রিনশট, অথবা শেয়ার্ড টেমিনালে সিক্রেট ফাঁস।

**সুপারিশ:** শুধমাত্র সিক্রেটের দৈর্ঘ্য বা হ্যাশ প্রিন্ট করুন:
```python
print(f"Success! Secret length: {len(secret.secret_value)}")
```

---

### গ্যাপ ১১: ফallback এনক্রিপশন কী (Fallback Encryption Key)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فાઇल** | `scripts/devops/upload_infisical.py:52` |
| **তীব্রতা** | 🔴 ক্রিটিক্যাল |
| **ধরণ** | এনক্রিপশন / সিকিউরিটি |

**কোড:**
```python
# upload_infisical.py:52
"ENCRYPTION_KEY": "supremeai-default-fallback-encryption-key-2026-v2"
```

**মূল কারণ:** একটি জানাল এনক্রিপশন কীকে সেক্রেট হিসেবে সরাসরি Infisical-এ আপলোড করা হয়েছে। যদি পরিবেশ পরিবর্তীতে এই কীটি সেট না থাকে, তাহলে পুরো সিস্টেম এই জানাল মান দিয়ে এনক্রিপ্ট করে — যা ক্রিপ্টোগ্রাফিকভাবে অপরিষ্কার।

**প্রভাব:** সবার কাছে একই এনক্রিপশন কী থাকে, যা এনক্রিপ্টেড ডাটা ডিক্রিপ্ট করতে পারে।

**সুপারিশ:** এনক্রিপশন কী অবশ্যই একটি নিরাপদ, র‍্যান্ডম, ভেজা-সিক্রেট থেকে পড়ুন। ডিফল্ট ফলাফল হিসেবে হ্যার্ডকোডেড মান যোগ দেবে না।

---

### গ্যাপ ১২: Gitleaks অ্যালোয়ালিস্ট দ্বন্দ্ব (Gitleaks Allowlist Conflict)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فایل** | `.gitleaks.toml:37-39` |
| **তীব্রতা** | 🔴 ক্রিটিক্যাল |
| **ধরণ** | সিকিউরিটি টুলিং / সিক্রীট ডিটেকশন |

**কোড:**
```toml
# .gitleaks.toml:37-39
allowlist = [
    "sk-[a-zA-Z0-9]{20,}",
    "rnd_[a-zA-Z0-9]{16,}",
    "eyJ[A-Za-z0-9_-]{10,}",
]
```

**মূল কারণ:** অ্যালোয়ালিস্টের রেগেক্স প্যাটার্নগুলো প্রকৃত সিক্রেট ফর্ম্যাটকে ম্যাচ করে:
- `sk-[a-zA-Z0-9]{20,}` — OpenAI API কী ফর্ম্যাট
- `rnd_[a-zA-Z0-9]{16,}` — Render সার্ভিস আইডি ফর্ম্যাট
- `eyJ[A-Za-z0-9_-]{10,}` — JWT টোকেন ফর্ম্যাট

**প্রভাব:** প্রকৃত সিক্রেটগুলি গিটলিকস ডিটেকশন থেকে বের হয়ে যায় এবং গিট ইতিহাসে সংরক্ষিত থাকে।

**সুপারিশ:** অ্যালোয়ালিস্ট থেকে এই জেনেরেটিক প্যাটার্নগুলো সরিয়ে ফেলুন। শুধমাত্র টেস্ট/ডকসের জন্য স্পষ্টতঃনির্দিষ্ট পাথ অ্যালোয়াল ব্যবহার করুন।

---

### গ্যাপ ১৩: পুরনো CI স্ক্রিপ্ট রেফারেন্স (Stale CI Script References)

| ক্ষেত্র | মান |
|--------|-----------------|
| **FILE** | `.github/workflows/maintenance.yml:722, 743, 906` |
| **তীব্রতা** | 🟡 মিডিয়ান |
| **ধরণ** | CI/CD স্ট্রাকচারাল |

**কোড:**
```yaml
# maintenance.yml:722
- name: Run Cost Guard
  run: "echo CI FIX: scripts/cost_guard_monitor.py does not exist — skipping"

# maintenance.yml:743
- name: Run AI Query Optimizer
  run: "echo CI FIX: scripts/ai_query_optimizer.py does not exist — skipping"

# maintenance.yml:906
run: |
  python -m pip install --quiet supabase
  python scripts/ci/render_recheck_scheduler.py
```

**মূল কারণ:** `cost_guard_monitor.py` এবং `ai_query_optimizer.py` ফাইলগুলো আছে না (এখন echo-এ কমে আছে)। কিন্তু `render_recheck_scheduler.py`-এর কমান্ডটি লাইভ (live) আছে — এটি `scripts/ci/render_recheck_scheduler.py` চায়, কিন্তু CI-এর `working-directory: backend` থেকে `backend/scripts/ci/render_recheck_scheduler.py` চায়। ফাইলটি রুটে `scripts/ci/` এ আছে, তাই পাথ মেলে না।

**প্রভাব:** CI জবটি `render_recheck_scheduler.py` স্টেপে ব্যর্ক হয়ে যায়।

**সুপারিশ:** পাথটি `../scripts/ci/render_recheck_scheduler.py`-এ আপডেট করুন অথবা `working-directory` সঠিক করুন।

---

### গ্যাপ ১৪: ভুল টাইপ অ্যানোটেশন (Incorrect Type Annotation)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فایل** | `backend/worker_service.py:153` |
| **তীব্রতা** | 🟢 লো |
| **ধরণ** | টাইপিং / কোড কোয়ালিটি |

**কোড:**
```python
# worker_service.py:153
result: Callable[..., Any] = getattr(tq, op)(*args, **kwargs)
return await result
```

**মূল কারণ:** `result`-এর টাইপ অ্যানোটেট করা হয়েছে `Callable[..., Any]` কিন্তু `getattr(tq, op)(*args, **kwargs)` একটি কোরুটিন রিটার্ন করে। `Callable` একটি কলযোগ্য অবজেক্টকে নির্দেশ করে, তবে এটি অবশ্যই কোরুটিন হতে হবে।

**সুপারিশ:**
```python
from collections.abc import Coroutine
result: Coroutine[Any, Any, Any] = getattr(tq, op)(*args, **kwargs)
```

---

### গ্যাপ ১৫: ডিক্রিপশন key_ref লজিক বাগ (Decryption key_ref Logic Bug)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فایل** | `backend/core/security/secure_credential_store.py:124-126` |
| **তীব্রতা** | 🟠 হাই |
| **ধরণ** | লজিক্যাল ফাঁপ / সিকিউরিটি |

**কোড:**
```python
# secure_credential_store.py:124-126
def decrypt(self, ciphertext: str, key_ref: str | None, ttl: int | None = None) -> str:
    if not self.enabled or not self.rotating_fernet or key_ref:
        return ciphertext
```

**মূল কারণ:** শর্তাংক `not self.enabled or not self.rotating_fernet or key_ref` — যখন `key_ref` সত্য (truthy) হয়, তখন `or` সংক্ষেপণ ফলে পুরো অভিব্যক্তি সত্য হয় এবং ফাংশনটি সিক্রেটটি ডিক্রিপ্ট না করে সরাসরি `ciphertext` রিটার্ন করে। অর্থাৎ, `key_ref` যখন আছে, তখনই ডিক্রিপশন স্কিপ করা হয় — যা সঠিক নয়।

**প্রভাব:** `key_ref` সহ যেকোনো সিক্রেট অপরিবর্তিত অবস্থায় থাকে — এটি ডিক্রিপ্ট করা হয়নি।

**সুপারিশ:** `key_ref` লজিকটি পুনর্নির্মাণ করুন। `key_ref` উপস্থিতি ডিক্রিপশন স্কিপ করা উচিত নয়; বরং `key_ref` দিয়ে সঠিক ফার্সেট নির্বাচন করা উচিত।

---

### গ্যাপ ১৬: /extract SSRF বাইপাস (SSRF Bypass in /extract Endpoint)

| ক্ষেত্র | মান |
|--------|-----------------|
| **FILE** | `backend/api/routes/browser.py:988-998` |
| **তীব্রতা** | 🟠 হাই |
| **ধরণ** | SSRF / নিরাপত্তা |

**کوড:**
```python
# browser.py:988-998
@router.post("/extract", dependencies=[Depends(require_admin_token)])
async def extract(url: str, extraction_prompt: str):
    """Fetch page and extract structured data with AI (Admin Only)."""
    from tools.browser.ai_web_extractor import AIWebExtractor
    extractor = AIWebExtractor()
    return await extractor.extract_data(url, extraction_prompt)
```

**মূল কারণ:** `extract` এন্ডপয়িন্টটি `url` প্যারামিটারকে সরাসরি `AIWebExtractor.extract_data(url, ...)` এ পাঠায় যেটি কোনো SSRF যাচাই না করে। যদিও `require_admin_token` আছে, তবুও যদি অ্যাডমিন টোকেন লিক হয়, তাহলে আক্রমণকারী ভ্যাজার্ড আকাশে (169.254.169.254), লোকালহুস্ট বা ভ্যাক্টার নেটওয়ার্কে অ্যাক্সেস করতে পারেন।

**প্রভাব:** ভ্যাজার্ড আকাশে এবং অভ্যন্তরীণ নেটওয়ার্ক থেকে তথ্য চুরি।

**সুপারিশ:** `is_safe_url(url)` চেক যোগ করুন (`browser.py:989`-এর আগে)। এটি নিশ্চিত করতে গ্যাপ ১-এর ইম্পোর্ট পাথ ঠিক করা প্রয়োজন।

---

### গ্যাপ ১৭: প্লেইনটেক্স্ট সিক্রেট রেসপন্সে (Plaintext Secret in Response)

| ক্ষেত্র | মান |
|--------|-----------------|
| **فایل** | `backend/api/routes/browser.py:427` |
| **तीব्रতা** | 🟡 মিডিয়ান |
| **ধরণ** | সিক্রেট এক্সপোজার |

**কোড:**
```python
# browser.py:427
"secret": decrypted_payload.get("password") or decrypted_payload.get("secret"),
```

**মূল কারণ:** `/credentials/{credential_id}/use` এন্ডপয়িন্টটি ডিক্রিপ্টেড সিক্রেট মানটিকে প্রত্যক্ষ HTTP রেসপন্স বডিতে ফেরত দেয়।

**প্রভাব:** সিক্রেট নেটওয়্যার্ক ট্রাফিক, লগ, ব্রাউজার ক্যাশে এবং প্রক্ষেপযোগ্য রাউটারে ফাঁস।

**সুপারিশ:** সিক্রেট সরাসরি রেসপন্সে ফেরত না দিয়ে, এটি সরাসরি টার্গেট রিকোয়েস্টের স্ট্রিমে ইনজেক্ট করুন বা সীমিত সময়ের URL জেনারেটর ব্যবহার করুন।

---

## ৫. সিক্রেট ও অথেনটিকেশন রিভিউ (Secret & Auth Review)

### ৫.১ সিক্রেট রিভিউ (Secret Review)

| সিক্রেট | ফাইল | আইডেন্টিফাইয়ার | অবস্থা |
|--------|----------------|-----------------|--------|
| `9f2363cf-3cec-43f6-b155-a8625de19250` | ৪টি স্ক্রিপ্ট | Infisical Client ID | 🔴 হ্যার্ডকোডেড |
| `92aa20c4-aef5-4e33-82bd-efb06058aaf0` | ৩টি স্ক্রিপ্ট | Infisical Project ID | 🔴 হ্যার্ডকোডেড |
| `srv-da666f8u01pc739bm3t0` | ২টি স্ক্রিপ্ট | Render Service ID | 🟡 হ্যার্ডকোডেড |
| `supremeai-default-fallback-encryption-key-2026-v2` | `upload_infisical.py` | Encryption Key | 🔴 ফলব্যাক ফাঁপ |
| `niloyjoy7@gmail.com` | `add_secrets_to_infisical.py` | Admin Email | 🟡 হ্যার্ডকোডেড |

### ৫.২ অথেনটিকেশন গ্যাপ (Authentication Gaps)

| এন্ডপয়িন্ট | ফাইল:লাইন | স্ট্যাটাস |
|-----------|:---:|--------|
| `/surf/skip-auth` | `browser.py:521` | ❌ কোনো অথেনটিকেশন নেই |
| `/browse-session` | `browser.py:774` | ⚠️ অথেনটিকেশন নেই (Crown Jewel) |
| `/ai-action` | `browser.py:779` | ⚠️ অথেনটিকেশন নেই (Crown Jewel) |

---

## ৬. সুপারিশ (Recommendations)

### ৬.১ অবিলম্বে করণীয় (P0 — Immediate)

1. **SSRF ইম্পোর্ট পাথ ঠিক করুন** — `core.security.ssrf_protection` → `core.security.protection.ssrf_protection` (`__init__.py:437`)।
2. **সব হ্যার্ডকোডেড সিক্রেট সরিয়ে ফেলুন** — ৪টি স্ক্রিপ্ট থেকে Infisical Client ID, Project ID এবং Render Service ID অপসারণ করে পরিবেশ পরিবর্তী ব্যবহার করুন।
3. **ফallback এনক্রিপশন কী সরিয়ে ফেলুন** — `upload_infisical.py:52`-এর মানটি সরাসরি পরিবেশ পরিবর্তী থেকে পড়ুন, ডিফল্ট ফলাফল হিসেবে হ্যার্ডকোডেড মান যোগ দেবে না।
4. **Gitleaks অ্যালোয়ালিস্ট পর্যালোচনা করুন** — `sk-[...]`, `rnd_[...]`, `eyJ[...]` জেনেরেটিক প্যাটার্নগুলো অ্যালোয়ালিস্ট থেকে সরিয়ে ফেলুন।

### ৬.২ ২৪ ঘণ্টার মধ্যে করণীয় (P1 — Within 24 Hours)

1. **PERMISSION_REQUESTS ডেড কোড মুছে ফেলুন** অথবা রিকোয়েস্ট পপুলেট করার এন্ডপয়িন্ট যোগ করুন (`browser.py:132`)।
2. **`/surf/skip-auth`-এ অথেনটিকেশন যোগ করুন** এবং এর নাম ও আচরণ পরিষ্কার করুন (`browser.py:521`)।
3. **Supabase বুটস্ট্র্যাপ স্কিমায় টেবিল যোগ করুন** — `render_account_states` এবং `render_preflight_events` (`supabase_client.py:210-778`)।
4. **ডিক্রিপশন key_ref লজিক পুনর্নির্মাণ করুন** — `secure_credential_store.py:125`-এর শর্তাংক সঠিক করুন।

### ৬.৩ ৭ দিনের মধ্যে করণীয় (P2 — Within 7 Days)

1. **`hash()` এর পরিবর্তে `hashlib`-এ রূপান্তর করুন** (`browser.py:776`)।
2. **আইডি জেনারেশনকে UUID-এ রূপান্তর করুন** (`browser.py:555, 564, 625`)।
3. **`/credentials/{id}/use`-এ সিক্রেট রেসপন্স থেকে বাদ দিনুন** (`browser.py:427`)।

### ৬.৪ নর্মাল রোডম্যাপ (P3/P4)

1. **টাইপ অ্যানোটেশন ঠিক করুন** (`worker_service.py:153`)।
2. **CI স্ক্রিপ্ট পাথ ঠিক করুন** — `maintenance.yml:906`।
3. **টেস্টে সিক্রেট প্রিন্টিং সরিয়ে ফেলুন** (`test_infisical.py:38, 52`)।
4. **/extract-এ SSRF ভ্যালিডেশন যোগ করুন** (`browser.py:988`)।
5. **হ্যার্ডকোডেড অ্যাডমিন ইমেল ও প্লেসহোল্ডার কী সরিয়ে ফেলুন** (`add_secrets_to_infisical.py:69-70`)।

### ৬.৫ গিট ট্র্যাকিং পরিষ্কার (Git Tracking Cleanup) — [✅ সম্পূর্ণ সমাধানকৃত]

- সেকশন ২-এ উল্লেখিত সমস্ত ফাইল বর্তমানে গিটে ট্র্যাক করা হয়েছে (`git ls-files` দ্বারা প্রতিপাদিত):
  - `backend/database/migrations/20_create_browser_credentials.sql` (✅ ট্র্যাকড)
  - `backend/models/render_account_state.py` (✅ ট্র্যাকড)
  - `backend/services/render_account_service.py` (✅ ট্র্যাকড)
  - `backend/api/routes/render_preflight_admin.py` (✅ ট্র্যাকড)
  - `backend/tests/test_render_account_service.py` (✅ ট্র্যাকড)
  - `frontend/src/components/admin/RenderPreflightWidget.tsx` (✅ ট্র্যাকড)
  - `frontend/src/utils/secureWebSocket.ts` (✅ ট্র্যাকড)
  - `scripts/ci/render_recheck_scheduler.py` (✅ ট্র্যাকড)
  - `scripts/generate_script_index.py` (✅ ট্র্যাকড)
- `backend/alembic_migrations/versions/2026_09_06_120000_add_render_account_state.py` ইতিমধ্যেই সক্রিয়ভাবে ট্র্যাক করা আছে।

---

## ৭. আর্তুলিপ্ত তথ্য (Appendix)

### A. আউটপুট ফর্ম্যাট স্ট্যান্ডার্ড

| সিম্বল | অর্থ |
|--------|------|
| 🔴 | ক্রিটিক্যাল — অবিলম্বে জোকেব করণীয় |
| 🟠 | হাই — ২৪ ঘণ্টার মধ্যে ঠিক করণীয় |
| 🟡 | মিডিয়ান — ৭ দিনের মধ্যে ঠিক করণীয় |
| 🟢 | লো — রোডম্যাপে ঠিক করা যাবে |

### B. রেফারেন্স ফাইল তালিকা

| গ্যাপ | ফাইল(গুলি) |
|-------|----------------|
| ১ | `backend/core/security/__init__.py`, `backend/core/security/protection/ssrf_protection.py` |
| ২, ৩, ৪, ৫, ১৬, ১৭ | `backend/api/routes/browser.py` |
| ৬ | `backend/database/supabase_client.py` |
| ৭, ৮, ৯, ১০ | `scripts/deploy/`, `scripts/devops/` |
| ১১ | `scripts/devops/upload_infisical.py` |
| ১২ | `.gitleaks.toml` |
| ১৩ | `.github/workflows/maintenance.yml` |
| ১৪ | `backend/worker_service.py` |
| ১৫ | `backend/core/security/secure_credential_store.py` |

---

**রিপোর্ট শেষ**