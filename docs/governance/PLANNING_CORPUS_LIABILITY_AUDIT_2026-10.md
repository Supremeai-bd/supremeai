# Planning-Corpus Liability Audit & Agent-Governance Cleanup — ২০২৬-১০

> **Status:** 🟢 Active — remediation roadmap (executed via linked issues)
> **তৈরি:** ২০২৬-১০-০৭ · **Verified against:** main @ `91bffd6`
> **লেখক-প্রসঙ্গ:** sandbox governance round (planner lane) — প্রশাসকের দুটি প্রস্তাবের ওপর ভিত্তি করে: (১) similar-problem agent rule, (২) planning liability audit
> **Related issues:** #4173 (Phase 0) · #4174 (U9 proposal) · #4175 (this audit's remediation) · #4176 (gate investigation)
> **🔒 নীতিগত সিদ্ধান্ত (প্রশাসক, ২০২৬-১০):** এই audit-এ **কোনো কিছুই delete হবে না** — superseded/obsolete সব কিছু `docs/archive/`-এ সরবে, আর প্রতিটি দলিলের মূল্যবান অংশ successor-এ তুলে নেওয়া হবে। Zero deletion, zero knowledge loss।

---

## ১. পটভূমি ও উদ্দেশ্য

প্রশাসক দুটি উন্নতির প্রস্তাব করেছেন। প্রথমত — agent-দের নিয়মে ছোট্ট সংযোজন: কেউ কোনো সমস্যা পেলে সেটাকে একক (isolated) সমস্যা হিসেবে না ধরে একই ধরনের আর কোনো occurrence আছে কি না খুঁজবে এবং applicable হলে ঠিক করবে বা follow-up করবে। দ্বিতীয়ত — বিভিন্ন সময়ে planning বদলানোর ফলে যেসব পুরনো পরিকল্পনা এখন আর liability (ক্ষতিকর/অপ্রয়োজনীয়) হয়ে দাঁড়িয়েছে, সেগুলোর তালিকা বানানো।

এই দলিল দুটোকেই এক initiative-এ বাঁধে: **Planning & Agent Governance Cleanup**। কারণ দুটো আসলে একই রোগের দুই লক্ষণ — knowledge এমনভাবে জমে যে navigation ভেঙে যায়, আর agent সমস্যা খুঁজে পেলেও তার ভাইবোন-occurrence খোঁজার দায়িত্ব ছাড়া চলে আসে।

## ২. পরিদর্শন-পদ্ধতি

প্রতিটি দাবি মুখস্থ-নয়, সরাসরি বর্তমান `main` (@ `91bffd6`) থেকে যাচাই করা হয়েছে — `AGENT_RULES.md`-এর fresh recheck, README/INDEX-এর প্রতিটি reference-এর line-level পরীক্ষা, git history ঘাঁটা, এবং planning corpus-এর প্রতিটি সক্রিয় দলিলের জন্য এই পাঁচ প্রশ্ন:

```text
দলিল → কোডবেসে কী implemented? → বর্তমান architecture-এর সঙ্গে compatible?
→ নতুন plan কি এটাকে replace করেছে? → কোনো সক্রিয় issue/PR নির্ভর করছে?
→ unique মূল্যবান অংশ আছে? → FINAL STATUS
```

## ৩. যাচাইকৃত আবিষ্কার

**F1 — Phantom canonical plan (সবচেয়ে গুরুতর navigation ত্রুটি)।** README তিন জায়গায় (L232 githistory লিংক, L240 "The full strategy lives in...", L733 "canonical baseline is now...") `docs/plans/architecture/SUPREMEAI_MASTER_PLAN_CANONICAL.md`-কে strategy-র উৎস বানিয়ে রেখেছে। `git log --all -- "*MASTER_PLAN_CANONICAL*"` → **শূন্য**। ফাইলটা git history-তে কোনোদিন ছিলই না। Agent-রা প্রতি রাউন্ডে SSoT re-read করে — অর্থাৎ প্রতিদিন এই ভাঙা রাস্তায় হাঁটছে। → #4173

**F2 — INDEX.md-এর নিজের drift।** INDEX দাবি করছে `docs/plans/`-এ শুধু একটাই ফাইল (`ARCH-LIVING-PIPELINE-01-IMPL.md`); বাস্তবে `docs/plans/architecture/SUPREMEAI_REPOSITORY_SEPARATION_AND_EVOLUTION_ROADMAP.md` সেখানে আছে এবং INDEX-এর কোথাও তার নাম নেই। শিক্ষা: drift শুধু পুরনো দলিলে নয়, গভর্নেন্স-দলিলেও জমে। → #4173

**F3 — rules.yml-এর stale allowlist entry।** `docs_garbage_policy.allowed_patterns`-এ `docs/DOCUMENTATION_MASTER_INDEX.md` আছে — ফাইলটা অস্তিত্বহীন। গভর্নেন্স-কনফিগেই মৃত reference। → #4173

**F4 — FRONTEND plan V1+V2 পাশাপাশি।** দুটোই ২০২৬-১০-০৬-এ #4149 (`9559081`) দিয়ে একসঙ্গে ঢুকেছে (V1: ৯৪৩ লাইন, V2: ১২৩২ লাইন)। V2-ই সক্রিয় execution-উৎস (theme-system v2 ফেজগুলো #4138/#4148); V1 সঙ্গে-সঙ্গে superseded। Conflict টাটকা অবস্থায় মেটানো সবচেয়ে সস্তা। → #4175

**F5 — docs_garbage gate নতুন non-allowlisted root docs আটকায়নি।** allowlist-এ না থেকেও F4-এর দুটি ফাইল gate পার হয়ে গেছে — ফাঁক (gap) নাকি অনুমোদিত ব্যতিক্রম, কিছুই রেকর্ডে নেই। Phase 4 (প্রতিরোধ)-এর ভিত্তি এই প্রশ্নের উত্তরের ওপর দাঁড়াবে। → #4176

**F6 — "Similar-problem sweep" নিয়মের অনুপস্থিতি।** `AGENT_RULES.md`-এ U1–U8 + P1–P6 আছে; P6 বলে ঠিক-করার সময় root-cause-class বন্ধ করতে, কিন্তু কেউ বাধ্য করে না আগে **class-টা আবিষ্কার** করতে। সাম্প্রতিক প্রমাণ: `ecosystem_scout/dedup.py`-র exact duplicate অলক্ষিত শিপ হয়েছিল (#4157)। → #4174

**F7 — ARCH-05 বনাম ROADMAP.md overlap।** `master_docs/ARCH-05-MASTER_ROADMAP_AND_DECISIONS.md` আর `docs/ROADMAP.md` দুটোই "roadmap" ভূমিকায় পাঠযোগ্য। দুটোই দরকার, কিন্তু সীমানা টানা জরুরি: ARCH-05 = সিদ্ধান্তের ইতিহাস-খাতা; ROADMAP = আজকের priority-তালিকা। → #4175

**F8 — সমসাময়িক প্রেক্ষাপট।** upstream ইতিমধ্যে dedup-কাজ করছে (#4157 exact-duplicate elimination, #4162 duplicate-dedup merge) — অর্থাৎ U9 ধারণাটা organically চলছে; rule বানালে সেটা formalize হবে, নতুন বোঝা হবে না।

## ৪. নীতিগত সিদ্ধান্ত: Archive-Only Remediation

পুরনো পরিকল্পনার মূল্যবান অংশ হারানো যাবে না — এটাই প্রশাসকের স্থায়ী নির্দেশ। তাই:

```text
পুরনো দলিল
   ↓
মূল্যবান তথ্য কী?
   ├── এখন প্রাসঙ্গিক → successor দলিলে extract
   ├── ঐতিহাসিক    → docs/archive/ (git history-তে সবসময় পুনরুদ্ধারযোগ্য)
   └── অপ্রয়োজনীয়  → তবুও archive-এই — delete নিষিদ্ধ
```

লক্ষ্য: **planning corpus-এর সক্রিয় navigation-পৃষ্ঠ ছোট করা, institutional knowledge হারিয়ে না।** এটা INDEX-এর zero-capability-loss নীতির (#2470) planning-corpus প্রয়োগ।

## ৫. Status Matrix (প্রতিটি সক্রিয় planning দলিলের verdict)

| # | দলিল | Status | ব্যবস্থা (archive-only) |
|---|-------|--------|------------------------|
| 1 | `docs/FRONTEND_DASHBOARD_MASTER_PLAN.md` (V1) | 🟠 Superseded | unique অংশ (budget/deliverables) V2-তে extract → `docs/archive/`-এ সরানো + `superseded_by: V2` হেডার। #4149-এর লেখক/প্রশাসকের সঙ্গে অভিপ্রায় নিশ্চিত করা বাধ্যতামূলক। |
| 2 | `docs/FRONTEND_DASHBOARD_MASTER_PLAN_V2.md` | 🟢 Active | রাখা — executed source। প্রশাসক-সিদ্ধান্ত: docs-root না `master_docs/FRONTEND-01`-এর পাশে। |
| 3 | `docs/ROADMAP.md` | 🟢 Active | রাখা — live priority roadmap, INDEX-এ টুলিং-সংযুক্ত। |
| 4 | `docs/plans/architecture/SUPREMEAI_REPOSITORY_SEPARATION_AND_EVOLUTION_ROADMAP.md` | 🟢 Active-aligned | INDEX-এ register + metadata header + ARCH-05-এর সঙ্গে সম্পর্ক। |
| 5 | `docs/master_docs/ARCH-05-MASTER_ROADMAP_AND_DECISIONS.md` | 🟡 Overlap-রেখা | রাখা; ROADMAP-এর সঙ্গে ২ লাইনের cross-reference। |
| 6 | `docs/INDEX.md` | 🟡 Keep-তারপর-mend | F2 মেরামত → #4173। |
| 7 | `docs/archive/**` | ⚪ Archive | যেমন আছে (১১টি আইটেম + lessons)। |
| 8 | README-র phantom refs | 🔴 Phantom | → #4173 (Phase 0)। |

## ৬. U9 প্রস্তাব — Similar-Problem Sweep

**বাংলা ব্যাখ্যা:** কোনো defect, antipattern, stale reference বা policy gap পাওয়া মাত্র প্রথম প্রশ্ন হবে — "এটা কি একা?" তারপর target করা sweep: একই pattern, একই ফাইল-পরিবার, একই reference-set, একই CI/checker-পৃষ্ঠ। একই root cause আর একই scope হলে একই task-এ (বা explicitly linked task-সারিতে) সমাধান; scope-বাইরে হলে linked follow-up issue। রিপোর্ট-ফরম্যাট: `similar found: N | fixed in-task: M | filed follow-up: K`।

**প্রস্তাবিত ইংরেজি পাঠ (AGENT_RULES.md §1-এ U8-এর পরে):**

> **U9 — Similar-Problem Sweep / Pattern-Aware Resolution**
> When any defect, antipattern, stale reference, or policy gap is found, the agent MUST NOT treat it as isolated by default. First classify: isolated one-off, or member of a defect/problem class? Perform a targeted sweep for sibling occurrences — same pattern, same file family, same reference-set, same CI/checker surface. If siblings share the same root cause AND the same scope, address them within the same task (or an explicitly linked task series) before closing the original. If they fall outside scope or risk, file linked follow-up issue(s) instead of silently expanding. Report format: `similar found: N | fixed in-task: M | filed follow-up: K`.
>
> **Similar ≠ blindly fix everything.** Evidence decides class membership; scope and safety decide the fix boundary. Scope-expanding mass changes without a sweep report are a contract violation.

**প্রতিফলন (৩টি mirror):** Coder-চুক্তিতে ১ লাইন (fix শেষ ঘোষণার আগে sweep + report); §4 Issue Creation Policy-তে checkbox ("similar occurrences swept?"); Auditor-এর clarify-duty-র পাশে sweep-duty।

**সম্পর্ক (সংঘর্ষহীন):** P6 = ঠিক-করার মুহূর্তে class বন্ধ করা; U9 = ঠিক-করার আগে/চলাকালীন class আবিষ্কার; U4 = existing-work-first-এর planning-প্রয়োগ।

**Guard-অবলম্বন:** `GUARD-SIMILAR-CLASS` এখনই নয় — আগে checkbox + role-duty, ৩–৪ সপ্তাহের sweep-report ডেটার পর P2-যাচাই করে সিদ্ধান্ত। (Complexity must earn its existence।)

## ৭. ধাপ-পরিকল্পনা

| Phase | কাজ | Issue | রানটাইম |
|-------|-----|-------|---------|
| **0 — Quick Fix** | README-র ৩ phantom ref + INDEX mend + rules.yml-এর stale line-out | #4173 | সবচেয়ে আগে; ঝুঁকি প্রায় শূন্য |
| **1 — U9 Rule** | governance অনুমোদন → AGENT_RULES.md + template checkbox | #4174 | প্রশাসক-সিদ্ধান্ত (§6) |
| **2–3 — Audit Remediation** | metadata headers, V1 extract+archive move, INDEX/README sync, ARCH-05↔ROADMAP cross-ref | #4175 | #4173-এর পর; প্রশাসক matrix ratify করলেই |
| **4 — প্রতিরোধ** | gate-gap বন্ধ; নতুন-plan-আগে-corpus-search; supersedes সম্পর্ক বাধ্যতামূলক; §8-এ plan-lifecycle | #4176 + পরবর্তী | তদন্ত → ফিক্স |

ক্রমের যুক্তি: Phase 0 সস্তা ও ঝুঁকিহীন বলে আগে; U9 অনুমোদন-পথে চলতে চলতে audit চলবে; আর audit নিজেই U9-এর প্রথম dogfooding — এই audit-এর F1–F3 একই root cause-এর ভাইবোন-occurrence হিসেবেই ধরা পড়েছে (sweep report: similar found 3, same root cause: un-swept findings)।

## ৮. ঝুঁকি ও সতর্কতা

1. **V1/V2 টাটকা** — গতকালই ঢুকেছে; হয়তো ইচ্ছাকৃত। তাই V1 archive-এর আগে #4149-এর অভিপ্রায় comment-এ জেনে নিতে হবে।
2. **rules.yml স্পর্শ** — governance-সংবেদনশীল; শুধু stale লাইন; scope-gate-এ shared-identity হলে disjoint-boundary justification।
3. **ROADMAP v1.2-এর Feature-vs-Refactor lock** — doc-cleanup architecture-branch নয়, নিরাপদ; তবু Phase-3 চলাকালীন নতুন planning-branch না খোলাই ভালো।
4. **বট-access অবস্থা** — এই রাউন্ডে দেখা গেছে পুরনো slots-এর অনেকগুলোর repo-permission নেই (probe দিয়ে নিশ্চিত); loop-নির্ভর automation আসলে কোন slot দিয়ে চলছে সেটা প্রশাসকের দৃষ্টিতে রাখা উচিত।

## ৯. প্রতিরোধ (Recurrence Prevention — Phase 4)

- নতুন plan খোলার আগে existing planning-corpus search **বাধ্যতামূলক** (U4-এর planning-সংস্করণ)।
- নতুন plan পুরনোটাকে replace করলে `supersedes` / `superseded_by` সম্পর্ক লেখা **বাধ্যতামূলক**।
- `docs_garbage` bypass-পথ বন্ধ বা স্পষ্ট-নথিভুক্ত ব্যতিক্রম-প্রক্রিয়া (#4176)।
- প্রতিটি বাঁচিয়ে-রাখা plan-এর হেডারে: `status` / `supersedes` / `superseded_by` / `last-reviewed`।
- §8 Document Circle-এ "plan lifecycle" ১ প্যারা: creation → review → supersede → archive (কখনোই delete নয়)।

## ১০. প্রমাণ-সংযোজনী (reproduction)

```bash
# F1: phantom ref — কোনোদিন অস্তিত্বেই ছিল না
git log --all --oneline -- "*MASTER_PLAN_CANONICAL*"          # → (empty)
sed -n '232p;240p;733p' README.md                             # → ৩টি reference

# F2: INDEX drift
grep -n "docs/plans" docs/INDEX.md; ls docs/plans/ docs/plans/architecture/

# F3: stale allowlist
grep -n "DOCUMENTATION_MASTER_INDEX" .github/constitution/rules.yml  # + ফাইল নেই

# F4/F5: #4149-এর নতুন দুটি root-doc
git show 9559081 --stat -- docs/FRONTEND_DASHBOARD_MASTER_PLAN.md docs/FRONTEND_DASHBOARD_MASTER_PLAN_V2.md

# F6: কোনো sweep-rule নেই
grep -niE "similar|sweep|same class" AGENT_RULES.md            # → sweep ধারণা অনুপস্থিত
```

---
*এই দলিল নিজেও U9-নীতিতে তৈরি: প্রতিটি দাবি fresh verification থেকে; কোনো দলিল বাদ দেওয়া হয়নি — বর্তমান corpus-এর প্রতিটি সদস্যের জন্য status নির্ধারিত।*
