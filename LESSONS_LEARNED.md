# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

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

## 2026-09-11 — 🔌 Backend/Frontend Parity Audit Remediation: Silent 404 Contracts & Unmounted Routers


- **সমস্যা:** ডিপ প্যারিটি অডিটে প্রমাণিত — (১) ফ্রন্টএন্ড দীর্ঘদিন ৪টি এমন এন্ডপয়েন্ট কল করছিল যা ব্যাকএন্ডে কখনোই ছিল না (`GET/POST /api/v1/health/agents`, `/admin/tenant-limits`, `/api/v1/agents/` GET list/status, `/api/admin/metrics/cost`) — প্রতিটি কল নীরবে 404 খেত (Swarm health, RateLimitManager, agentService, useBudgetCheck); (২) ৭টি কার্যকর ব্যাকএন্ড রাউটার (`diagram_to_architecture`, `voice_coder`, `ai_pair_programmer`, `self_planner`, `video_to_code_pipeline`, `vulnerability_prophet`, `ws/command_center`) `ALL_ROUTERS`-এ ছিল না বলে বুট থেকেই dead ছিল।
- **ফিক্স:** `health.py`-তে GET+POST `/health/agents` (agent_supervisor.get_health + agent_ids ফিল্টার, unknown id → status="unknown"); `billing_api.py`-তে wallet-ভিত্তিক `GET /api/billing/budget-check` (estimated > balance হলে 402 Payment Required); ৭টি রাউটার `ALL_ROUTERS`-এ মাউন্ট (registry prefix="" — প্রতিটির নিজস্ব prefix আছে; voice_coder-এ WS রুট থাকায় is_admin=False sibling pattern)। ফ্রন্টএন্ড: RateLimitManager → `/admin-api/tenant-limits`, agentService → `/api/agents/*`, useBudgetCheck → `/api/billing/budget-check`; navigationRegistry-তে /research, /scheduled-tasks, /memory, /settings/api-keys implemented হিসেবে exposed; SecretsPage `/settings/api-keys` রাউটেড; MCPConnector IntegrationsManager-এর নতুন 'MCP Servers' tab-এ embedded।
- **লেসন:** Contract drift ধরতে runtime-evidence cross-system audit আবশ্যক — mounted-but-unregistered রাউটার ও frontend-এর legacy পাথ দুটোই নীরব 404 তৈরি করে। ফিক্সগুলো `tests/security/test_dead_route_wiring.py`-এ regression guard হিসেবে লক করা হয়েছে। টেকনিক্যাল নোট: FastAPI-র নতুন `_IncludedRouter` wrapper ব্যবহার করলে route ভেরিফিকেশনে `original_router` traversal + `include_context.prefix` প্রয়োগ করতে হয় — top-level `app.routes`-এ include prefix প্রয়োগ হয় না।
