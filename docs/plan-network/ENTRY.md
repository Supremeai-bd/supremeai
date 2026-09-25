---
id: plan-network-entry
subject: "SupremeAI Plan Network — Consolidation Entry Point"
document_role: architecture
planning_authority: Architecture Governance / Planning Circle
canonical: true
status: active
evidence_state: verified
disposition: retain
last_verified: 2026-09-25
supersedes:
  - "docs/DOCUMENTATION_MASTER_INDEX.md (as the human-readable index)"
target_scope: combined_ecosystem
---

# SupremeAI Plan Network — Entry Point

> **একটা সিস্টেমের প্রতিটি মডিউল, কম্পোনেন্ট — একটা আরেকটার প্রতিযোগী না।**
> **সব মিলে একটা ফুল সিস্টেম হয়।** তেমনি আমাদের প্ল্যানগুলো — কোনোটা কোনোটার
> বিপরীত বা প্রতিযোগী না। সবগুলো একটা ইকোসিস্টেমের অংশ।

**তৈরি:** 2026-09-25 · **AGENTS.md compliance:** ✅ · **দর্শন:** [ECOSYSTEM_PHILOSOPHY.md](./ECOSYSTEM_PHILOSOPHY.md)

---

## কোথা থেকে শুরু করবেন

| যদি চান... | পড়ুন |
|---|---|
| ইকোসিস্টেম দর্শন বুঝতে | [ECOSYSTEM_PHILOSOPHY.md](./ECOSYSTEM_PHILOSOPHY.md) ← **প্রথমে এটি** |
| ৭টি চিরন্তন কোর প্ল্যান (আলাদা আলাদা নথি) | [core-plans/](./core-plans/README.md) & [বিবর্তন](../CORE_PLANS_EVOLUTION.md) |
| **সব প্ল্যান কীভাবে ৭ কোর-এ যুক্ত** | **[CORE_PLANS_CONNECTION_MAP.md](./CORE_PLANS_CONNECTION_MAP.md)** |
| **Wave Master Plan (৪৩ কাজ, ৬ Wave)** | **[WAVE_MASTER_PLAN.md](./WAVE_MASTER_PLAN.md)** |
| **Validation Phase (Wave-এর পরের production-ready যাত্রা)** | **[VALIDATION_PHASE_ROADMAP.md](./VALIDATION_PHASE_ROADMAP.md)** |
| ১৮৩ ফাইলের বিস্তারিত বিশ্লেষণ | [ANALYSIS_REPORT.md](./ANALYSIS_REPORT.md) |
| ১২ ক্যানোনিকাল প্ল্যানের ইনডেক্স | [plans/PLAN_REGISTRY.md](./plans/PLAN_REGISTRY.md) |
| ডিপেন্ডেন্সি গ্রাফ | [plans/PLAN_GRAPH.md](./plans/PLAN_GRAPH.md) |
| ফাইলের ভূমিকা নির্ধারণ ম্যাপ | [plans/MIGRATION_MAP.md](./plans/MIGRATION_MAP.md) |
| নতুন প্ল্যান যোগ করতে | [plans/IMPACT_MAP.md](./plans/IMPACT_MAP.md) |

---

## এক লাইনে পুরো প্ল্যান

```
Capability খোঁজো → Run চালাও → Verify করো → Memory-তে রাখো → Approval ↺
```

এই লুপটা হলো গাছের কাণ্ড। বাকি সব — প্ল্যান, মডিউল, কোড — এর চারপাশে
শাখা-প্রশাখা হিসেবে গজিয়েছে। কেউ অপ্রয়োজনীয় না; প্রতিটার ভূমিকা আছে।

---

## ৫টা চুক্তি (পুরো সিস্টেম এই লুপে চলে)

| # | চুক্তি | প্রশ্ন | বর্তমান অবস্থা |
|---|---|---|---|
| **C1** | Capability Registry | "আমার কাছে কী আছে?" | MCP Tower ~৮০ টুল ✅, কিন্তু ৮+ প্রোভাইডার লিস্ট ভাসছে ⚠️ |
| **C2** | Canonical Run | "কীভাবে এক্সিকিউট করি?" | `backend/runs/` ১২-স্টেট ✅, কিন্তু ১/৮ RunType জেগে ⚠️ |
| **C3** | Verify Gate | "কিভাবে জানব কাজ হয়েছে?" | pass^k + ৬২ মিশন + STATUS_PROOF ✅ |
| **C4** | Memory Write | "পরের টাস্ক সস্তা হবে?" | ৩-পিলার ডিজাইন আছে, কিন্তু ১৫ স্টোর ⚠️ |
| **C5** | Governed Approval | "কখন মানুষ অ্যাপ্রুভ করে?" | ৭টা স্টেট মেশিন, কেউ সম্পূর্ণ না ⚠️ |

বিস্তারিত: [ECOSYSTEM_PHILOSOPHY.md](./ECOSYSTEM_PHILOSOPHY.md)

---

## ১৮৩ ফাইলের ভূমিকা (কেউ বর্জন নয়)

| ভূমিকা | সংখ্যা | গাছের অংশ |
|---|---|---|
| ক্যানোনিকাল | ~২৫ | আজকের মূল শাখা |
| মার্জ | ~২০ | ছোট শাখা বড় শাখায় জুড়ে গেছে |
| আর্কাইভ রেফারেন্স | ~৯০ | পুরনো পাতা — মাটিতে মিশে শিকড়ের খোরাক |
| শুকনো ডাল | ~৪৮ | আলাদা করা দরকার, কিন্তু মুছলে ইতিহাস হারায় |

> **নিয়ম:** কাউকে মুছবে না। প্রতিটাকে তার ভূমিকা দাও।
> বিস্তারিত: [plans/MIGRATION_MAP.md](./plans/MIGRATION_MAP.md)

---

## এক্সিকিউশন ঋতু (একসাথে একটাই Wave)

| ঋতু | Wave | কাজ | সময় |
|---|---|---|---|
| 🌸 বসন্ত | Wave ০ | সেফটি নেট | ১ সপ্তাহ |
| ☀️ গ্রীষ্ম | Wave ১ | ফাউন্ডেশন আনব্লক | ২ সপ্তাহ |
| 🍂 শরৎ | Wave ২ | ট্রুথ পার্জ | ২ সপ্তাহ |
| ❄️ শীত | Wave ৩ | কনসোলিডেশন | ৪ সপ্তাহ |
| 🌱 নতুন বসন্ত | Wave ৪ | ডেলিভারি | ৪ সপ্তাহ |
| 🌳 পূর্ণতা | Wave ৫ | ভেরিফিকেশন | চলমান |

বিস্তারিত: [ANALYSIS_REPORT.md](./ANALYSIS_REPORT.md) §8

---

## এই প্যাচে কী আছে

```text
docs/plan-network/                    ← overlay (main-এ merged)
├── ECOSYSTEM_PHILOSOPHY.md           ← ইকোসিস্টেম দর্শন (canonical)
├── ENTRY.md                          ← এই ফাইল
├── ANALYSIS_REPORT.md                ← ১৮৩ ফাইল বিশ্লেষণ
├── README.md + PATCH_README.md
├── vision/principles.md              ← Layer 1
├── architecture/system.md + domains.md  ← Layer 2
├── plans/
│   ├── PLAN_REGISTRY.md              ← ১২ ক্যানোনিকাল প্ল্যান
│   ├── PLAN_GRAPH.md                 ← mermaid গ্রাফ
│   ├── PLAN_MATRIX.md, PLAN_STATUS_LIFECYCLE.md
│   ├── IMPACT_MAP.md, MIGRATION_MAP.md
│   ├── _templates/PLAN_TEMPLATE.md
│   └── ১২টা প্ল্যান (P01-P12)
├── execution/github-mapping.md       ← Layer 4
└── verification/audits.md + production-checks.md  ← Layer 5
```

---

## AGENTS.md compliance

- [x] **§4 Branch Isolation:** কখনো `main`-এ push নয়
- [x] **§4 Branch Pattern:** `docs/.+` OPS-06 pattern
- [x] **§6 Narrowest Change:** শুধু নতুন docs, কোনো existing ফাইল স্পর্শ নয়
- [x] **§6 Reuse Before Creation:** `docs/plan-network/` subfolder-এ
- [x] **§9 Zero Regression:** কোনো কোড/টেস্ট পরিবর্তন নয়
- [x] **§13 Atomic PR:** এক branch, এক focused PR
