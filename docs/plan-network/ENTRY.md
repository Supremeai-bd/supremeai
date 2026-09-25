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

# SupremeAI Plan Network — Consolidation Entry Point

> **এই ফাইলটি হলো নতুন Plan Network-এর এন্ট্রি পয়েন্ট।**
> ১৮৩টি ছড়িয়ে থাকা প্ল্যান ফাইলকে ১২টি ক্যানোনিকাল প্ল্যানে রূপান্তর করে,
> একটি relationship layer যোগ করে, এবং ফাইনাল প্রোডাক্টের জন্য একটি
> সিম্পল-বাট-ইফেক্টিভ মেকানিজম প্রস্তাব করে।
>
> **এটি কোনো existing ফাইল মুছে না** — শুধু নতুন organized overlay যোগ করে।
> Legacy `docs/plans/` ফাইলগুলো `docs/archive/plans/`-এ সরানো হবে
> `MIGRATION_MAP.md` অনুযায়ী, পৃথক PR-এ।

**তৈরি:** 2026-09-25 · **বেস কমিট:** `535ba33` · **AGENTS.md compliance:** ✅

---

## কী কী যোগ হয়েছে (এই PR-এ)

```text
docs/plan-network/                    ← নতুন overlay (২৯ ফাইল)
├── ENTRY.md                          ← এই ফাইল (এন্ট্রি পয়েন্ট)
├── README.md                         ← ডকুমেন্টেশন এন্ট্রি
├── PATCH_README.md                   ← কীভাবে এপ্লাই করবেন
├── ANALYSIS_REPORT.md                ← ১৮৩ ফাইল বিশ্লেষণ রিপোর্ট (৫১৯ লাইন)
├── vision/principles.md              ← Layer 1: ৭টা principle
├── architecture/
│   ├── system.md                     ← Layer 2: ৫-লেয়ার মডেল
│   └── domains.md                    ← Layer 2: ৯টা domain
├── plans/
│   ├── PLAN_REGISTRY.md              ← THE index (১২ প্ল্যান)
│   ├── PLAN_GRAPH.md                 ← mermaid dependency graph
│   ├── PLAN_MATRIX.md                ← dependency + reverse matrix
│   ├── PLAN_STATUS_LIFECYCLE.md      ← ৭-স্টেট স্টেট মেশিন
│   ├── IMPACT_MAP.md                 ← new-plan intake checklist
│   ├── MIGRATION_MAP.md              ← ১৮৩ → ১২ mapping
│   ├── _templates/PLAN_TEMPLATE.md   ← canonical template
│   ├── security/         (P01)       ← ১২ ক্যানোনিকাল প্ল্যান
│   ├── intelligence/     (P02, P05)
│   ├── mcp/              (P03)
│   ├── agents/           (P04)
│   ├── automation/       (P06)
│   ├── experience/       (P07)
│   ├── infrastructure/   (P08)
│   ├── observability/    (P09)
│   └── governance/       (P10, P11, P12)
├── execution/github-mapping.md       ← Layer 4: plan → milestone → issue
└── verification/
    ├── audits.md                     ← Layer 5: audit surfaces
    └── production-checks.md          ← Layer 5: SLOs + runtime hooks
```

---

## ফাইনাল প্রোডাক্টের জন্য সিম্পল-বাট-ইফেক্টিভ মেকানিজম

> এটি `ANALYSIS_REPORT.md` থেকে সিনথেসিস করা মূল উত্তর।
> ১৮৩টা প্ল্যান পড়ে বের হওয়া এক-লাইন মেকানিজম।

```
Capability খোঁজো → Run চালাও → Verify করো → Memory-তে সংরক্ষণ → Approval ↺
```

### ৫টা চুক্তি (পুরো সিস্টেম এই লুপে চলে)

| # | চুক্তি | প্রশ্ন | বর্তমান অবস্থা |
|---|---|---|---|
| **C1** | Capability Registry | "আমার কাছে কী আছে?" | MCP Tower ~৮০ টুল ✅, কিন্তু ৮+ প্রোভাইডার লিস্ট ভাসছে ⚠️ |
| **C2** | Canonical Run | "কীভাবে এক্সিকিউট করি?" | `backend/runs/` ১২-স্টেট ✅, কিন্তু ১/৮ RunType জেগে ⚠️ |
| **C3** | Verify Gate | "কিভাবে জানব কাজ হয়েছে?" | pass^k + ৬২ মিশন টেস্ট + STATUS_PROOF ✅ |
| **C4** | Memory Write | "পরের টাস্ক সস্তা হবে?" | ৩-পিলার ডিজাইন আছে, কিন্তু ১৫ স্টোর ⚠️ |
| **C5** | Governed Approval | "কখন মানুষ অ্যাপ্রুভ করে?" | ৭টা স্টেট মেশিন, কেউ সম্পূর্ণ না ⚠️ |

**কেন সিম্পল-বাট-ইফেক্টিভ:** প্রতিটা ডুপ্লিকেশন এই লুপ ভাঙে —
৯ রেট-লিমিটার → C1-এ একটা, বাকি ৮ ডিলিট।
৬ LLM গেটওয়ে → C1-এ একটা, Zero-Bypass Boundary দ্বারা এনফোর্স।
৩৬ মেমরি ফাইল → C4-এ একটা canonical write path।

---

## ১৮৩ ফাইলের ভারডিক্ট (বিশ্লেষণ থেকে)

| বিভাগ | সংখ্যা | অর্থ |
|---|---|---|
| ক্যানোনিকাল (রাখবে) | ~২৫ | আসল সত্যের উৎস |
| মার্জ করা দরকার | ~২০ | ভালো কন্টেন্ট, ডুপ্লিকেট |
| আর্কাইভ রেফারেন্স | ~৯০ | ইতিহাস, পড়তে হবে না |
| বাদ/স্টেল | ~৪৮ | জাভা যুগ, কন্ট্রাডিক্টরি |

বিস্তারিত প্রতিটা ক্লাস্টারের ফলাফল `ANALYSIS_REPORT.md`-এ।

---

## এক্সিকিউশন অর্ডার (AGENTS.md single-plan discipline অনুযায়ী)

একসাথে একটাই Implementing। বিস্তারিত `ANALYSIS_REPORT.md` §8-এ।

1. **Wave 0 — সেফটি নেট** (১ সপ্তাহ): DB hazard বন্ধ, backup drill, এই প্যাচ এপ্লাই
2. **Wave 1 — ফাউন্ডেশন আনব্লক** (২ সপ্তাহ): M03 InferenceContext, M01 Memory, M06 run_scope, M09 ReAct
3. **Wave 2 — ট্রুথ পার্জ** (২ সপ্তাহ): M21 Truth-Mirror, false-assurance পার্জ
4. **Wave 3 — কনসোলিডেশন** (৪ সপ্তাহ): ৯→১ রেট-লিমিটার, ৬→১ গেটওয়ে, ৩৬→domain মেমরি
5. **Wave 4 — ডেলিভারি** (৪ সপ্তাহ): M10 Frontend, M18 Telegram, M17 HITL, M19 i18n
6. **Wave 5 — ভেরিফিকেশন মোট** (চলমান): pass^k CI gate, per-service probe, স্কোরবোর্ড

---

## এই PR-এর স্কোপ

**এই PR শুধু ডকুমেন্টেশন যোগ করে** — কোনো কোড পরিবর্তন নয়, কোনো legacy ফাইল মুছে না।

- ✅ ২৯টি নতুন ফাইল `docs/plan-network/`-এ
- ✅ কোনো existing ফাইল পরিবর্তন নয়
- ✅ কোনো কোড/কনফিগ/টেস্ট স্পর্শ নয়
- ✅ AGENTS.md §4 branch isolation মানা (`docs/` prefix, একটাই PR)
- ✅ AGENTS.md §6 narrowest sound change (শুধু নতুন docs)

**পরবর্তী PR-এ কী হবে** (এই PR-এর বাইরে):
- `MIGRATION_MAP.md` অনুযায়ী legacy `docs/plans/` ফাইলগুলো `docs/archive/plans/`-এ সরানো
- `DOCUMENTATION_MASTER_INDEX.md` (৩০৫KB) আর্কাইভ করে এই এন্ট্রি পয়েন্টকে canonical করা

---

## কীভাবে রিভিউ করবেন

1. `ANALYSIS_REPORT.md` পড়ুন — ১৮৩ ফাইলের পূর্ণ বিশ্লেষণ (৫১৯ লাইন)
2. `README.md` পড়ুন — Plan Network-এর স্ট্রাকচার
3. `plans/PLAN_REGISTRY.md` দেখুন — ১২ ক্যানোনিকাল প্ল্যানের ইনডেক্স
4. `plans/PLAN_GRAPH.md` দেখুন — mermaid dependency graph
5. `plans/MIGRATION_MAP.md` দেখুন — ১৮৩ → ১২ mapping

রিভিউ শেষ হলে merge করুন। তারপর Wave 0-এর পরবর্তী ধাপ (legacy archival) আলাদা PR-এ।

---

## AGENTS.md compliance চেকলিস্ট

- [x] **§3 Issue-First:** এই PR নিজেই একটি কাজের ইউনিট (doc consolidation)
- [x] **§4 Branch Isolation:** `docs/plan-network-consolidation` branch, কখনো `main`-এ push নয়
- [x] **§4 Branch Pattern:** `docs/.+` OPS-06 pattern মেনে চলে
- [x] **§5 Main Sync:** latest `origin/main` (`535ba33`) থেকে তৈরি
- [x] **§6 Narrowest Change:** শুধু নতুন docs, কোনো existing ফাইল স্পর্শ নয়
- [x] **§6 Reuse Before Creation:** `docs/plan-network/` subfolder-এ রেখে existing `docs/plans/`-এর সাথে কনফ্লিক্ট এড়ানো
- [x] **§9 Zero Regression:** কোনো কোড/টেস্ট পরিবর্তন নয়, তাই regression অসম্ভব
- [x] **§13 Atomic PR:** একটাই branch, একটাই PR, focused scope
