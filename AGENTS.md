<!-- GENERATED FILE — DO NOT EDIT BY HAND -->
<!-- Source of truth: .github/constitution/rules.yml · Generator: scripts/ci/generate_agents_md.py -->
<!-- CI drift check: system-gates.yml → agents-md-sync. To change rules, edit rules.yml. -->


# SupremeAI — AGENTS.md v2 (Full-Freedom Bootstrap)

> rules_version: `2.0` · যতই ঘুড়ি উড়াও রাতে, নাটাই তো আমার হাতে।
>
> Agent-কে আর নিয়ম মুখস্থ করতে হবে না — যা করতে পারবে না, system নিজেই আটকাবে এবং কারণ বলে দেবে।
>
> নিয়ন্ত্রণ তোমার হাতে নয় — SYSTEM-এর হাতে। তাই তোমাকে নিয়ম মুখস্থ করতে হবে না।
> যা করতে পারবে না, system নিজেই আটকাবে এবং কারণ বলে দেবে।

---

## Bootstrap (৩ ধাপ)

1. `python scripts/agents/acquire_role_slot.py --role <lane>` — slot + mesh lease (lease না থাকলে push-ই হবে না)
2. `./scripts/agents/next_claimable.sh <lane>` — সর্বোচ্চ-অগ্রাধিকার unclaimed issue চেয়ে নাও
3. `কাজ করো। উড়ো। যেভাবে ভালো বোঝো সেভাবে সমাধান করো।`

Full rule map: [`docs/agents/RULES_INDEX.md`](docs/agents/RULES_INDEX.md) · Priority order: [`docs/agents/ISSUE_PRIORITY_POLICY.md`](docs/agents/ISSUE_PRIORITY_POLICY.md)

---

## System যা আটকাবে (মনে রাখার দরকার নেই — শুধু জেনে রাখো কেন আটকালো)

| Gate | কখন আটকাবে | Enforcement |
| :--- | :--- | :--- |
| Lease Gate | PR head branch লেখকের leased slot-এর বাইরে (bot slot-mismatch), বা mesh lease মেয়াদ শেষ | CI (system-gates.yml) |
| Verification Gate | PR description-এ Test Evidence সেকশন নেই (টেস্ট লগ/কমান্ড আউটপুট ছাড়া PR BLOCK) | CI (system-gates.yml) |
| Scope Gate | claim-এ declare করা 'Touching files:'-এর বাইরের ফাইল PR-এ বদলালে BLOCK | CI (system-gates.yml) |
| Collision Gate | অন্য open PR-এর ফাইলের সাথে direct overlap হলে BLOCK | CI (pr-gate.yml (check-collisions, strict mode #2002)) |
| Self-Merge Gate | নিজের PR নিজে approve/merge করলে BLOCK | branch protection + pr-helper review |
| Test Guard | test delete/skip/threshold-নামানো হলে BLOCK | constitution audit engine extension |
| Post-Merge Watch | merge-এর ১৫ মিনিটের মধ্যে main লাল হলে auto-revert | merge-train land job |

---

## তোমার স্বাধীনতা (কেউ আটকাবে না)

- সমাধানের approach নিজে বেছে নাও — architecture, pattern, library (stack অগ্রাধিকার মানলে ভালো, বাধ্য না)
- যেকোনো unclaimed issue চেয়ে নাও (lane-অগ্রাধিকার advisory, আটকানো নয়)
- আটকে গেলে blocker issue খোলো এবং পরের কাজে যাও — চুপচাপ বসে থেকো না
- ভুল হলে LESSONS_LEARNED.md-তে এক লাইন যোগ করো — শাস্তি নেই, পুনরাবৃত্তি-প্রতিরোধই লক্ষ্য

---

## একমাত্র কঠিন নিয়ম (মোট ৩টা, বাকি সব system-এর ভার)

1. সৎ থাকো — কাজ 'দেখতে ভালো' না, 'সত্যিই ভালো' হতে হবে (test manipulation = সর্বোচ্চ অপরাধ)
2. পরমাণু থাকো — এক PR এক উদ্দেশ্য
3. চলমান থাকো — শেষ হলে পরের issue; আটকালে জানাও

---

> সম্পূর্ণ machine-readable rule registry: `.github/constitution/rules.yml` (CI এটা থেকে gate চালায়)।
> **এই file-টি registry থেকে GENERATED — হাতে এডিট করবে না।**
