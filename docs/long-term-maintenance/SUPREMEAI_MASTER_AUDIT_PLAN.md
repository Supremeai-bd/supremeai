# SupremeAI 2.0 — Full Project Audit Master Plan (0% → 100%)

**উদ্দেশ্য:** পুরো `supremeai` মনোরিপো (backend + 5টা app + packages + infra) root থেকে systematically audit করা — security bug, silent error, dead/fake-success কোড, config drift, docs-vs-code মিথ্যা claim — সব ধরনের ইস্যু বের করা, প্রতিটা claim verify-সহ।

**কিভাবে ব্যবহার করবেন:**
এই পুরো ফাইলটা লোকাল AI (Claude Code) এর কাছে দিন। প্রতিদিন বলুন: *"AUDIT_PLAN.md পড়ো, Phase N চালাও, শেষে PHASE_LOG.md আপডেট করো।"* — একদিনে একটা Phase-এর বেশি না করাই ভালো (context/quality-এর জন্য)।

---

## ০. গ্লোবাল রুলস (সব Phase-এ বাধ্যতামূলক — AI-কে এই সেকশন প্রতিবার আগে পড়াবেন)

1. **কোনো ইস্যু "Fixed" লেখা যাবে না যতক্ষণ না প্রমাণ (grep count / test output / diff) দেখানো হয়েছে।** শুধু prose summary ("এখন ঠিক আছে") গ্রহণযোগ্য না।
2. **একবারে পুরো Phase-এর সব ফাইল "পড়েছি" দাবি করা যাবে না** — যদি ফাইল সংখ্যা বেশি হয়, sub-batch-এ ভাগ করে প্রতিটা batch শেষে ফাইল কাউন্ট রিপোর্ট করতে হবে (কতটা পড়া হলো / কতটা বাকি)।
3. **প্রতিটা ইস্যুর ফরম্যাট বাধ্যতামূলক:**
   ```
   [ID] [Severity: P0/P1/P2/P3] [ফাইল:লাইন]
   সমস্যা: (এক লাইনে)
   কেন এটা সমস্যা / root cause: (২-৩ লাইন)
   প্রমাণ: (কোড স্নিপেট বা grep আউটপুট)
   সাজেস্টেড ফিক্স: (fix পরে, আলাদা approval-এর পর করা হবে — এই ধাপে শুধু ইস্যু লিস্ট)
   ```
4. **Severity taxonomy:**
   - **P0** — secret leak, RCE/injection, auth bypass, data loss risk, production down করতে পারে এমন কিছু
   - **P1** — fake/mocked success (কাজ করছে বলে দাবি করে কিন্তু persist/execute করে না), silent exception swallow যা ডেটা করাপশন ঘটাতে পারে
   - **P2** — config drift (IaC বনাম বাস্তব deploy), dead code, ডুপ্লিকেট লজিক, resource leak
   - **P3** — style, missing test, minor perf, TODO/FIXME স্তূপ
5. **Fix করার আগে approval লাগবে** — audit ও fix আলাদা ধাপ। Phase-এর কাজ শুধু *খুঁজে বের করা ও রিপোর্ট করা*, নিজে থেকে কোড পাল্টে ফেলা না (যদি না user "ঠিক করে দাও" বলে)।
6. **প্রতিটা Phase শেষে self-verification ধাপ বাধ্যতামূলক** — AI নিজেই grep/count চালিয়ে নিজের ৩টা প্রধান finding প্রমাণ করে দেখাবে। এটা স্কিপ করা যাবে না।
7. **Docs-কে সোর্স অফ ট্রুথ হিসেবে ধরা যাবে না** — `docs/bangla/*AUDIT*` বা যেকোনো README-তে "✅ Fixed/Done" লেখা থাকলেও কোড গিয়ে সরাসরি verify করতে হবে (কারণ আগেই একটা এমন মিথ্যা claim পাওয়া গেছে — CSP বাগ শুধু ১টা ফাইলে ফিক্স হয়ে বাকি ৩টায় হয়নি)।
8. প্রতিটা Phase-এর শেষে `PHASE_LOG.md`-এ এন্ট্রি যোগ করবে (ফরম্যাট নিচে ধাপ "মাস্টার লগ"-এ)।

---

## 📐 Error-Check ক্রম (small → big)

প্রতিটা Phase-এর ভেতরে কোন ধরনের error আগে খুঁজবেন, কোনটা পরে — তার বিস্তারিত ক্রম ও যুক্তি দেওয়া আছে [`CODE_QUALITY_CHECK_SEQUENCE.md`](./CODE_QUALITY_CHECK_SEQUENCE.md)-এ (syntax → lint → dead code → bare except → import cycles → types → tests → security → architecture)। প্রতিটা Phase শুরুর আগে এই ফাইলটা একবার পড়ে নিন।

---

## Phase 0 — সেটআপ ও বেসলাইন (আজ, ~১-২ ঘণ্টা)

**লক্ষ্য:** টুলিং বসানো, ফাইল ইনভেন্টরি, স্ট্যাটিক অ্যানালাইজার রান করা যাতে AI-এর pure-LLM অনুমানের উপর নির্ভর করতে না হয়।

কাজ:
1. রিপো রুটে ফাইল ইনভেন্টরি বানাও: প্রতিটা top-level ফোল্ডারে কতগুলো ফাইল, কোন ভাষা।
2. স্ট্যাটিক টুল চালাও (থাকলে, না থাকলে ইন্সটল করে):
   - Python: `ruff check .`, `bandit -r backend`, `mypy` (যেখানে config আছে)
   - TS/JS: `eslint .` (studio-client, vscode-extension, packages-এ)
   - Dart: `flutter analyze` (mobile)
   - Secrets: `git secrets`/`gitleaks` দিয়ে পুরো git history স্ক্যান (আগে একটা লিক হওয়া JWT secret পাওয়া গিয়েছিল, ইতিহাসে আরও থাকতে পারে)
3. `PHASE_LOG.md` ফাইল বানাও (root-এ) — টেমপ্লেট নিচে।
4. এই প্ল্যানের Phase 1-16 এর তালিকা `PHASE_LOG.md`-এ "Not Started" স্ট্যাটাসসহ বসাও।

---

## Phase তালিকা (ফাইল কাউন্টসহ — বাস্তব রিপো অনুযায়ী)

| Phase | মডিউল | আনুমানিক ফাইল | ফোকাস |
|---|---|---|---|
| 1 | `backend/core/` | 205 | সবচেয়ে বড়/গুরুত্বপূর্ণ — orchestration core, security-critical |
| 2 | `backend/api/` + `middleware/` + `database/` | ~104 | Route auth, input validation, DB access pattern |
| 3 | `backend/agents/` + `brain/` + `adaptive_engine/` + `evolution/` | ~86 | Agent logic, self-evolution — fake-success risk বেশি এখানে |
| 4 | `backend/tools/` + `scripts/` + `utils/` | ~154 | Utility/tool কোড — dead code বেশি থাকতে পারে |
| 5 | `backend/memory/` + `skills/` + `models/` + `schemas/` + `storage/` | ~55 | ডেটা মডেল ও পার্সিস্টেন্স সঠিকতা |
| 6 | `backend/p2p/`, `byoc/`, `workers/`, `sandbox/`, `ws/`, `monitoring/`, `services/`, `scout/`, `pipelines/`, `reports/`, `admin/` | ~43 | ছোট মডিউলের গুচ্ছ — sandbox/exec risk বিশেষভাবে দেখা |
| 7 | `backend/tests/` | 367 | টেস্ট **quality** audit — টেস্ট আছে মানেই কাজ করে তা না; সব pass কিন্তু কিছু test করছে না এমন কিছু আছে কিনা |
| 8 | `apps/studio-client/` (web frontend) | 348 | API client consistency (আজ যেমন দুটো apiClient পাওয়া গেছে), auth token storage, XSS |
| 9 | `tools/vscode-extension/` (বাকি অংশ, CSP বাদে) | 50 | Command registration সব কাজ করে কিনা, webview↔extension message contract |
| 10 | `apps/mobile/` (Flutter) | 92 | Token storage, deep link handling, hardcoded API URL |
| 11 | `apps/desktop-app/` + `apps/java-worker/` + `apps/hf-space/` | — | Electron security (nodeIntegration/contextIsolation), Dockerfile secret |
| 12 | `infrastructure/` + `cloudflare-worker/` + `config/` + `configs/` + `render.yaml`/`render.admin.yaml`/docker-compose/terraform | — | IaC বনাম বাস্তব deploy mismatch (render.yaml gap-এর মতো আরও আছে কিনা) |
| 13 | `packages/` + `shared/` + root `src/` + root `skills/` | ~20+ | Shared code — একটা বাগ থাকলে multiple app-এ ছড়ায় |
| 14 | Dependency/CVE scan | সব | `npm audit`, `pip-audit`, `flutter pub outdated`, license check |
| 15 | Docs-vs-Code সামঞ্জস্য পাস | সব `docs/bangla/*AUDIT*`, README | প্রতিটা "✅ Fixed/Done" claim কোডে গিয়ে re-verify |
| 16 | ফাইনাল ইন্টিগ্রেশন পাস | — | Critical flow end-to-end trace (login → chat → billing → agent execution), মাস্টার রিপোর্ট + prioritized roadmap |

> বড় প্রজেক্ট (২৩৬৭+ ফাইল), তাই ১৬ দিন/সেশন লাগতে পারে। চাইলে ২-৩টা ছোট Phase একদিনে একসাথে করানো যায় (যেমন Phase 6 + 13), কিন্তু Phase 1, 7, 8 আলাদা রাখাই ভালো (বড়/ক্রিটিক্যাল)।

---

## প্রতিদিন ব্যবহারের প্রম্পট টেমপ্লেট

```
SUPREMEAI_FULL_AUDIT_PLAN.md ফাইলটা পড়ো।
আজ Phase [N] চালাও: [মডিউল পাথ]।

নিয়ম (Section ০ থেকে):
- Fixed বলার আগে প্রমাণ দাও
- ব্যাচে পড়ো, প্রতি ব্যাচ শেষে ফাইল কাউন্ট রিপোর্ট করো
- ইস্যু ফরম্যাট মেনে চলো (ID/Severity/ফাইল:লাইন/কারণ/প্রমাণ)
- এখনই fix কোরো না, শুধু ইস্যু লিস্ট দাও
- Phase শেষে নিজে grep/count দিয়ে টপ ৩ finding verify করে দেখাও
- PHASE_LOG.md-এ এন্ট্রি যোগ করো

শেষে আমাকে সংক্ষেপে বলো: কতগুলো P0/P1/P2/P3 পাওয়া গেছে, আর কালকের Phase [N+1] শুরু করার আগে কিছু জানা দরকার কিনা।
```

---

## মাস্টার লগ ফরম্যাট (`PHASE_LOG.md`-এ প্রতিটা Phase শেষে এই এন্ট্রি)

```markdown
## Phase [N] — [মডিউল নাম] — [তারিখ]
- ফাইল কভারেজ: X/Y পড়া হয়েছে
- পাওয়া গেছে: P0=?, P1=?, P2=?, P3=?
- Top 3 findings (ID সহ):
  1. ...
  2. ...
  3. ...
- Self-verification স্ট্যাটাস: ✅ grep/test দিয়ে প্রমাণিত | ⚠️ আংশিক | ❌ শুধু prose claim
- পরবর্তী Phase-এর জন্য নোট: ...
```

এই লগ ফাইলটাই আপনার "single source of truth" — কোনদিন কী পাওয়া গেছে, কী এখনো ভেরিফাই হয়নি, সব একনজরে দেখা যাবে।

## অডিট ও ফিক্স ট্র্যাকিং টেবিল ফরম্যাট (Audit & Fix Tracking Table)

প্রতিটি Phase অডিট ও ফিক্স করার পর নতুন কোনো ফাইল তৈরি না করে, একক স্থায়ী ফাইল **[AUDIT_FIX_TRACKER.md](file:///f:/supremeai%20backup/docs/audit_reports/AUDIT_FIX_TRACKER.md)**-এ অডিট ও ফিক্স ট্র্যাকিং টেবিলটি মেইনটেইন করতে হবে। সকল AI এজেন্ট সর্বদা এই নির্দিষ্ট ফাইলে নতুন রেকর্ড যোগ বা আপডেট করবে।

### স্ট্যান্ডার্ড এরর টাইপসমূহ (Standard Error Types):
1. **Syntax Error (`P1`):** কোড সিনট্যাক্স বা ফরম্যাটজনিত ত্রুটি।
2. **Static Lint (`P3`):** কোডিং স্ট্যান্ডার্ড বা স্টাইল গাইডলাইন ভায়োলেশন (যেমন: Unused Imports)।
3. **Dead Code (`P2`):** অব্যবহৃত বা অপ্রয়োজনীয় কোড সেকশন।
4. **Silent Failure (`P1`):** ট্রাই-এক্সেপ্ট ব্লক দিয়ে এরর ধামাচাপা দেওয়া (e.g., bare `except: pass`)।
5. **Circular Dependency (`P2`):** মডিউলসমূহের মধ্যে চক্রাকার নির্ভরশীলতা।
6. **Type Mismatch (`P2`):** ফাংশন বা ভেরিয়েবলের টাইপ অসঙ্গতি।
7. **Security Bug (`P0`):** হার্ডকোডেড এপিআই কি/সিক্রেট, SQL ইনজেকশন রিস্ক ইত্যাদি।
8. **Config Drift (`P2`):** লোকাল কনফিগারেশন বনাম রিয়েল ক্লাউড ডেপ্লয়মেন্টের অসঙ্গতি।
9. **Logic/UI Mismatch (`P2`):** এপিআই ইন্টারফেস বা এপিআই ক্লায়েন্টের লজিক্যাল অমিল।
10. **Fake-Success (`P1`):** কোড সফলভাবে সম্পন্ন হয়েছে বলে দাবি করে কিন্তু বাস্তবে ডাটাবেস বা এক্সটার্নাল এপিআইতে কোনো প্রভাব ফেলে না (Mocks/Stubs প্রোডাকশনে থেকে যাওয়া)।
11. **Resource Leak (`P2`):** ফাইল বা ডাটাবেস কানেকশন হ্যান্ডলার সঠিকভাবে বন্ধ (close) না করা।
12. **Race Condition (`P1`):** সমান্তরাল রিকোয়েস্ট বা অ্যাসিঙ্ক অপারেশনের ডেটা করাপশন বা কনফ্লিক্ট।
13. **Secret Sync Drift (`P0`):** একাধিক প্ল্যাটফর্মের (GitHub, Vercel, Render ইত্যাদি) মধ্যে এনভায়রনমেন্ট ভ্যারিয়েবল বা সিক্রেট সিঙ্ক না থাকা।

### অডিট ও ফিক্স ট্র্যাকিং টেবিল স্ট্রাকচার:

| File Name (পাথ) | Error Type (এররের ধরন ও Severity) | Fix Time (ফিক্সের সময়) | Fixed By Whom (কার দ্বারা ফিক্সড) | Reverified By (ভেরিফায়ার ও প্রমাণ) | Status (অবস্থা) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `example/auth_core.py` | Security Bug / P0 | 2026-08-07 05:25 | Antigravity AI | Pytest + Admin Verify | ✅ Fixed & Verified |
| `example/db_helper.py` | Silent Failure / P1 | 2026-08-07 05:30 | Antigravity AI | Pytest | ✅ Fixed & Verified |
| `example/old_utils.py` | Dead Code / P2 | 2026-08-07 05:40 | Antigravity AI | manual check | ✅ Fixed & Verified |
| `example/style.ts` | Static Lint / P3 | — | — | — | ⚠️ Pending |

---


## Phase 16 শেষে (ফাইনাল রিপোর্ট)

সব Phase শেষ হলে AI-কে বলুন:
```
PHASE_LOG.md-এর সব এন্ট্রি একসাথে করে একটা কনসোলিডেটেড রিপোর্ট বানাও:
1. সব P0 ইস্যু এক জায়গায়, ফিক্স-অর্ডার priority সহ
2. মডিউল ধরে ধরে risk heatmap (কোন মডিউলে সবচেয়ে বেশি P0/P1)
3. এমন কোনো cross-module প্যাটার্ন আছে কিনা যেটা বারবার ঘটছে (যেমন: duplicate API client লজিক, fake-success pattern) — সেগুলো আলাদা করে হাইলাইট করো
```

---

## আমার সাজেশন (ভালো আইডিয়া হিসেবে যোগ করছি)

1. **শুধু LLM-এর অনুমানের উপর নির্ভর না করে static tool + AI hybrid করুন** (Phase 0-এ যোগ করা হয়েছে) — `bandit`/`ruff`/`eslint`/`gitleaks` প্রথমে concrete সিগন্যাল দেবে, AI সেটার উপর ভিত্তি করে বিশ্লেষণ করলে hallucination অনেক কমে।
2. **প্রতিটা Phase-এর "Fixed" claim একটা *ফ্রেশ* AI সেশনে (বা পরদিন) আবার cross-check করান** — একই সেশনে যে AI ফিক্স করেছে, সে নিজের ভুল স্বীকার করতে দ্বিধা করতে পারে। নতুন সেশনে "এই claim-টা সত্যি কিনা grep করে দেখাও" জিজ্ঞেস করলে exactly আজকের CSP বাগের মতো জিনিস ধরা পড়বে।
3. **PHASE_LOG.md রিপোতেই কমিট রাখুন** (git-এ) — তাহলে সময়ের সাথে audit history ট্র্যাক থাকবে, আর ভবিষ্যতে কোনো AI সেশন context হিসেবে পুরনো findings পড়তে পারবে।
4. **Phase 7 (tests) আর Phase 15 (docs) স্কিপ করবেন না** — এই দুইটাই সাধারণত সবচেয়ে অবহেলিত, অথচ এখানেই "সব ঠিক আছে বলে দাবি" আর "বাস্তবে যা হচ্ছে" এর গ্যাপ সবচেয়ে বেশি ধরা পড়ে।
