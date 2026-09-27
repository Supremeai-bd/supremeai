# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-09-27 — 🧩 Monkeypatch-Proof Dependency Resolution: function-level `from`-import শ্যাডো-attribute বাইপাস (#2098)

- **Issue:** #2098 — CI-only 4× `"Event loop is closed"` failure in core-unit rate-limit tests; local runs সবসময় pass করত।
- **সমস্যা:** `_check_rate_limit`-এর ভেতরে function-level `from core.cache.redis_manager import redis_manager` লেখা হয়েছিল। `core/cache/__init__.py` singleton-টিকে submodule-এর নিজ নামে re-export করে, ফলে CI-র import sequence-এ import টি **shadowed package attribute** resolve করে — test-এর module-attr monkeypatch সম্পূর্ণ বাইপাস হয়ে গিয়ে REAL singleton-এ পৌঁছায়। প্রমাণ: CI log-এ `⚡ Serverless Upstash Redis REST Provider Active` পুরো run-এ ঠিক ১ বার, সেটাও *টেস্টের ভেতরেই* — fake-এর `eval_calls == 0`।
- **Fix:** `backend/core/middleware/security.py`-এ sys.modules-first resolution (`_get_redis_manager()`) — call-time-এ সবসময় আসল module object-এর (patch-করা) attribute দেয়; production-এ দুই পথই একই singleton, behavior identical। PR #2110।
- **লেসন:** (১) `package/__init__`-এ same-name re-export থাকলে function-level `from package.module import name` **patch-proof নয়** — test যা monkeypatch করে সেটি বাইপাস হতে পারে; (২) monkeypatch-target dependency call-site-এ `sys.modules` lookup বা `import package.module as m; m.name` আকারে resolve করো; (৩) "dependency-র init log ঠিক টেস্টের ভেতরে ১ বার" মানেই real dependency টেস্ট চলাকালীন initialize হয়েছে — patch bypass-এর smoking gun।

## 2026-09-12 — ⚡ MANDATORY RULE #1: Zero Local-Machine Dependency & Start-of-Conversation Recall Mandate

- **সমস্যা:** ম্যানুয়াল লোকাল পিসি ও লোকাল টার্মিনালনির্ভর নির্দেশ বা প্লাগইন কনফিগারেশন দিলে তা ক্লাউড-ফার্স্ট/প্রডাকশন আর্কিটেকচার এবং ব্যবহারকারীর ওয়ার্কফ্লোকে ব্যাহত করে।
- **ফিক্স:** `AGENTS.md`-এর চূড়ায় **MANDATORY RULE #1** সংস্থাপিত করা হয়েছে—১% কাজ বা প্ল্যানিংও লোকাল পিসির ওপর নির্ভর করা যাবে না। প্রতিটি এআই এজেন্টকে প্রতি কনভার্সেশনের শুরুতে Rule #1 রিফাইন ও এনফোর্স করতে হবে। সব সার্ভিস (Backend, Frontend, MCP, CI/CD) প্রথম দিন থেকেই ১০০% অটোমেটেড ক্লাউড-নেটিভ প্রডাকশন ইঞ্জিনে চলবে (No Exception)।
- **লেসন:** জিরো লোকাল ডিপেন্ডেন্সি ও কনভার্সেশনের শুরুতে বাধ্যতামূলক রিকল হলো SupremeAI-এর এক নম্বর সাংবিধানিক নিয়ম।

## 2026-09-12 — 🏛️ Core Philosophy Reinforcement: Zero-Hardcoding Mandate & System-Wide Universal Rule Scoping


- **সমস্যা:** কোডবেস বা সিস্টেমে যেকোনো হার্ডকোডেড ভ্যালু (লজিক, প্রম্পট, ইউআরএল, কনফিগারেশন, পলিসি) ফ্লেক্সিবিলিটি নষ্ট করে। একই সাথে কোনো একটি সুনির্দিষ্ট মডিউল (যেমন: MCP Server) নিয়ে শেখা নিয়ম বা নির্দেশ সেকশন-আইসোলেটেড মনে করার ঝুঁকি তৈরি হতে পারে।
- **ফিক্স:** `AGENTS.md` (Section 1)-এ ২টি মৌলিক সার্বজনীন ফিলোসোফি আপডেট করা হয়েছে: (১) **Zero-Hardcoding Mandate** — সিস্টেমে কোনো কিছুই হার্ডকোড করা যাবে না; সব ড্যাশবোর্ড/ডিবি থেকে ডাইনামিকভাবে নিয়ন্ত্রণযোগ্য হতে হবে; (২) **Universal Rule Scoping** — একটি মডিউলে শেখা নিয়ম বা গার্ডরেল কখনো আইসোলেটেড থাকবে না, তা Backend, Frontend, AI Agents, Docs, CI/CD জুড়ে **সামগ্রিক SupremeAI প্রজেক্টে সার্বজনীনভাবে (System-Wide)** কার্যকর হবে।
- **লেসন:** হার্ডকোডিং মুক্ত ডাইনামিক ডিজাইন এবং সিস্টেম-ওয়াইড ইউনিভার্সাল রুল স্কোপিং হলো SupremeAI-এর ক্যানোনিকাল আর্কিটেকচারের মূল ভিত্তি।

## 2026-09-12 — 🛡️ Security Audit Execution: 30-Category Matrix + Gap-Closing Hardening Tests


- **সমস্যা:** ৩০-ক্যাটাগরি OWASP/AppSec/AI-Agents অডিটে প্রমাণিত — নিয়ন্ত্রণগুলো (controls) ইতিমধ্যে বিদ্যমান (CSRF, Redis rate limiter, ToolPolicyGateway, SSRF protection, JWT prod secret ≥64-byte guard, SHA-pinned CI), কিন্তু কয়েকটি **static-টেস্ট gap** ছিল: (১) `DANGEROUS_PATTERNS`-এ শুধু `\.\./` ছিল — hex/double-encoded path traversal (`%2e%2e%2f`, `%252e%252e%252f`) বাইপাস করত; (২) JWT `alg:none`/tamper/expired, client-IP `X-Forwarded-For` spoof, SSRF private/loopback/metadata, mass-assignment — কোনোটির dedicated test ছিল না; (৩) OWASP checklist-এর evidence path ছিল stale (`app/middleware/auth.py` অস্তিত্বহীন)।
- **ফিক্স:** (১) `backend/core/middleware/security.py`-তে ৭টি encoded-traversal pattern যোগ; (২) `backend/tests/security/test_hardening_controls.py` (২৯টি test — JWT alg:none, Tamper, Expired, client-IP spoof resistance, SSRF private/loopback/metadata/DNS-rebinding, WAF SQLi/XSS/encoded-traversal, mass-assignment) — **সব ২৯ PASS**; (৩) OWASP checklist evidence path আপডেট + `docs/security/SECURITY_AUDIT_MATRIX.md` (৩০-category verified matrix) + `docs/security/dast/ZAP_DAST_GATE.md` (Phase C DAST design, staging-নির্ভর)।
- **লেসন:** (১) source-level/unit test pattern (app fixture ছাড়া) security tier-এ দ্রুত ও নির্ভরযোগ্য — `tests/security/` অটো critical-tier; (২) "scanner-এ vulnerability type আছে" ≠ "অ্যাপ নিরাপদ" — প্রতিটি control-এর behavior-level test দরকার; (৩) pre-existing env-related failures (`aiosqlite`-না-থাকা, MCP `getaddrinfo` mock) static audit-কে যাচাই করার সময় baseline-এ আলাদা করতে হয়; (৪) credential-less staging ছাড়া DAST/IDOR runtime test সম্ভব না — `ZAP_DAST_GATE.md` deploy-gate design-এ লক করা হয়েছে।

- **সমস্যা:** ব্যাকএন্ড এপিআই, ফ্রন্টএন্ড ওয়েব অ্যাপ, ডকুমেন্টেশন, এআই এজেন্ট বা রিমোট কানেকশনে bare `http://localhost...` লিঙ্ক দিলে রিমোট এআই বা ক্লাউড সার্ভিস সার্ভিসগুলোর সাথে কানেকশন ফেইল করে।
- **ফিক্স:** `AGENTS.md`-তে ইউনিভার্সাল রুল ৬ সিস্টেম-ওয়াইড বিস্তৃত করা হয়েছে—সামগ্রিক SupremeAI প্রজেক্টের (Backend APIs, Frontend, Docs, MCP, AI Agents) যেকোনো কানেকশন বা নির্দেশনায় bare `localhost` ব্যবহার সম্পূর্ণ নিষিদ্ধ। সবসময় প্রডাকশন ডোমেইন লিঙ্ক (`https://...onrender.com`) অথবা লাইভ টানেল এন্ডপয়েন্ট (`cloudflared`/`ngrok`) রেকমেন্ড করতে হবে।
- **লেসন:** ক্লাউড সার্ভিস বা রিমোট ক্লায়েন্ট কখনো ডিভাইসের লোকাল লুপব্যাক আইপি (`127.0.0.1`/`localhost`) এক্সেস করতে পারে না; পুরো সুপ্রিমএআই ইকোসিস্টেমে পাবলিকলি এক্সেসিবল এন্ডপয়েন্ট বা টানেল বাধ্যতামূলক।
