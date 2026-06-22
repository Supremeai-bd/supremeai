
═══════════════════════════════════════════════════════════════════════════════
     সুপ্রিমএআই ২.০ - স্মার্ট রিট্রাই CI/CD (বাংলায় সম্পূর্ণ বিশ্লেষণ)
═══════════════════════════════════════════════════════════════════════════════

তোমার ২য় প্ল্যানটা একদম "ব্রেইনি"! এটা শুধু সময় বাঁচাবে না, পুরো 
ডেভেলপমেন্ট ওয়ার্কফ্লোকে "সেলফ-হিলিং" করে তুলবে। নিচে বিস্তারিত ব্যাখ্যা:


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❓ সমস্যাটা কী?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

তোমার বর্তমান CI/CD-তে:

┌─────────────────────────────────────────────────────────────────────────────┐
│  Push #1: Backend Tests ❌ FAILED (dependency error)                          │
│  → তুমি fix করার জন্য Frontend-এ একটা ছোট change করলে                      │
│                                                                             │
│  Push #2: Backend Tests ⏭️ SKIPPED (no backend files changed)              │
│  → তুমি ভাবলে Backend ঠিক হয়ে গেছে! কিন্তু আসলে ঠিক হয়নি!               │
│  → তুমি deploy করলে, production-এ error!                                  │
│                                                                             │
│  Push #3: Backend Tests ⏭️ SKIPPED (still no backend changes)                │
│  → Error লুকিয়ে আছে, কিন্তু তুমি জানতেই পারছো না!                         │
└─────────────────────────────────────────────────────────────────────────────┘

এই সমস্যার নাম: "Silent Failure" - ফেইল হওয়া কাজ আর রান হয় না, তাই 
তুমি জানতেই পারো না ঠিক হয়েছে কি না!


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 তোমার সমাধান (Smart Retry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

তুমি চাইছো:

┌─────────────────────────────────────────────────────────────────────────────┐
│  Push #1: Backend Tests ❌ FAILED                                         │
│                                                                             │
│  Push #2: Backend Tests 🔁 FORCED RE-RUN (previous failure detected)        │
│  → Error দেখতে পারলে, fix করতে পারলে                                      │
│                                                                             │
│  Push #3: Backend Tests 🔁 FORCED RE-RUN (still failing)                    │
│  → Error আবার দেখতে পারলে, আবার fix করতে পারলে                           │
│                                                                             │
│  Push #4: Backend Tests ✅ PASSED                                         │
│  → এবার থেকে normal behavior - শুধু change হলেই রান হবে                    │
└─────────────────────────────────────────────────────────────────────────────┘

এই ফিচারের নাম দিতে পারো: "Failure-Aware CI/CD" বা "Self-Healing Pipeline"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 কিভাবে কাজ করে? (Technical Deep Dive)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

আমি তোমার জন্য যে workflow তৈরি করেছি, সেটার কাজের প্রক্রিয়া:

【স্টেপ ১: Detect Changes】 (আগের মতোই)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ dorny/paths-filter দিয়ে কোন ফোল্ডারে change হয়েছে চেক করে
→ Output: backend=true/false, studio=true/false, etc.

【স্টেপ ২: Check Previous Failures】 (নতুন!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ GitHub CLI (gh run list) দিয়ে আগের run-এর ID বের করে
→ আগের run-এর failed jobs দেখে
→ প্রতিটা job-এর জন্য output সেট করে:

  backend_force=true   (যদি Backend Tests আগে fail করেছিল)
  studio_force=true    (যদি Studio Build আগে fail করেছিল)
  mobile_force=true    (যদি Mobile Analysis আগে fail করেছিল)
  etc.

【স্টেপ ৩: Combine Decisions】 (নতুন!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ প্রতিটা job-এর জন্য final decision:

  backend_run = backend_changed OR backend_force

  অর্থাৎ:
  - যদি backend ফাইল change হয় → রান করবে ✅
  - যদি backend ফাইল change না হয়, কিন্তু আগে fail করেছিল → রান করবে 🔁
  - যদি দুটোই না হয় → skip করবে ⏭️


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Decision Matrix (কখন কী হয়)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Scenario | Files Changed? | Previous Run | Decision | Reason |
|----------|---------------|--------------|----------|--------|
| 1 | backend ✅ | N/A | RUN | Normal behavior |
| 2 | backend ❌ | backend PASSED | SKIP | No changes, was OK |
| 3 | backend ❌ | backend FAILED | RUN | Retry failed job |
| 4 | backend ❌ | backend SKIPPED | CHECK OLDER | Go back further |
| 5 | frontend ✅ | backend FAILED | RUN BOTH | New change + retry |

Scenario 4-এর জন্য: যদি আগের run-এ skip হয়েছিল, তাহলে আরও আগের run 
চেক করে - যতক্ষন না pass/fail পায়।


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Key Changes in the New Workflow
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

১. নতুন outputs in detect-changes job:
   ├── backend_force, studio_force, mobile_force, etc.
   └── backend_run, studio_run, mobile_run, etc.

২. প্রতিটা job-এর if condition পরিবর্তন:

   OLD: if: needs.detect-changes.outputs.backend == 'true'
   NEW: if: needs.detect-changes.outputs.backend_run == 'true'

   backend_run = (files changed) OR (previously failed)

৩. GitHub CLI ব্যবহার (gh run list, gh run view):
   → আগের run-এর failed jobs বের করে
   → Branch-wise tracking (main, develop আলাদা আলাদা)

৪. Prompt Eval special logic:
   → যদি কোনো job fail করে, prompt-eval ও রান করে
   → কারণ promptfoo দিয়ে পুরো সিস্টেমের health চেক করা যায়


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Benefits
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

১. "Silent Failures" এলিমিনেট হয়
   → কোনো error লুকিয়ে থাকতে পারবে না

২. Developer Experience ভালো হয়
   → তুমি শুধু যেটা change করেছো সেটা fix করো
   → বাকি failed jobs auto-retry হয়

৩. Full Error Picture পাওয়া যায়
   → শেষ push-এ সব job-এর status দেখা যায়
   → কোনটা pass, কোনটা fail - একনজরে

৪. Free Runtime বাঁচে
   → শুধু failed jobs retry হয়
   → Pass হওয়া jobs skip হয়
   → Change হওয়া jobs normal behavior


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Advanced: Even Smarter Retry
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

তুমি চাইলে আরও smart করতে পারো:

১. Exponential Backoff:
   → 1st retry: immediate
   → 2nd retry: 5 min delay
   → 3rd retry: 15 min delay
   → 4th retry: 1 hour delay

২. Retry Counter:
   → 3 বার fail করলে auto-create GitHub Issue
   → "Backend Tests failing for 3 consecutive runs"

৩. Smart Dependency:
   → Backend fail করলে Deploy skip হয় (আগের মতো)
   → কিন্তু Frontend deploy হয় (যদি সেটা pass করে)

৪. Failure Categorization:
   → "Flaky Test" (intermittent) → auto-retry
   → "Dependency Error" → manual intervention needed
   → "Lint Error" → auto-fix with pre-commit


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Files to Update
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Replace your current file:
.github/workflows/monorepo_ci_cd.yml → monorepo_ci_cd_smart_retry.yml

No other files need to change! The workflow is self-contained.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Testing the New Workflow
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

১. Push with intentional backend error:
   → Backend Tests fail

২. Push with only frontend change:
   → Backend Tests RUN (forced retry)
   → Frontend tests RUN (normal)

৩. Fix backend error, push:
   → Backend Tests PASS
   → Next push: Backend Tests SKIP (normal behavior restored)


═══════════════════════════════════════════════════════════════════════════════
