# Harvest Manifest — group:foundation-closeout (seq:2)

> **তারিখ:** 2026-09-28 21:57 UTC · **ইঞ্জিন:** `scripts/supremeai_toolkit/harvest.py` · **roots:** scripts · **অডিট-বেস:** 400 ফাইল
> **Golden Rule:** ছাঁটাইয়ের আগে harvest — beneficial লজিক প্রথমে ক্যানোনিকাল মডিউলে, পরে খোসা।
> এই ম্যানিফেস্ট রায়-প্রমাণ মাত্র — নিজে কিছু ডিলিট করে না (read-only)।

## রায়-সারসংক্ষেপ (prune-candidate প্রার্থীদের গভীর পরীক্ষা)

| রায় | সংখ্যা | অর্থ |
| :--- | ---: | :--- |
| keep-operational | 7 | অপারেশনাল ডক/পরিবার-প্রমাণ — স্পর্শ নিষিদ্ধ |
| keep-canonical | 0 | repair-pairing/merge-হোম — রিপেয়ারে জীবন্ত হবে |
| absorb-then-prune | 1 | আগে toolkit-এ পুনঃসৃষ্ট, পরে ছাঁটাই |
| prune-after-harvest | 10 | প্রমাণিত অরফ্যান — ছাঁটাইযোগ্য |

## ফাইল-ভিত্তিক রায়

### ✂️ `scripts/apply_plan_renames.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 0 def, 0 class, 81 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/ci/update_ci_comments.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 39 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/consolidate_identical_plans.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 0 def, 0 class, 55 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### 🛡️ `scripts/deploy/check_render_auto_deploy.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 23 লাইন
- manual-override: DRY Phase 2-C3 render_client পরিবার — পোর্টেবল, exit-code-সচেতন; runbook-অ্যাঙ্করড sibling update_render_image.py পরিবারের অপারেশনাল প্রমাণ

### 🛡️ `scripts/deploy/create_render_service.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 27 লাইন
- manual-override: DRY Phase 2-C3 render_client পরিবার — service-lookup টুল; runbook-অ্যাঙ্করড sibling প্রমাণ

### 🛡️ `scripts/deploy/list_render_services.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 22 লাইন
- manual-override: DRY Phase 2-C3 render_client পরিবার — service-inventory টুল; runbook-অ্যাঙ্করড sibling প্রমাণ

### 🛡️ `scripts/deploy/update_infisical_render.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 54 লাইন
- অপারেশনাল ডক-রেফ: docs/master_docs/ARCH-02-SYSTEM_OVERVIEW_AND_FLOWS.md, docs/master_docs/DEVOPS-01-PURE_CLOUD_INFRASTRUCTURE.md, docs/operations/BACKUP_RESTORE_AND_ROLLBACK.md

### 🛡️ `scripts/deploy/update_render_env2.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 37 লাইন
- manual-override: DRY Phase 2-C3 render_client পরিবার — env-var ম্যানেজমেন্ট; runbook-অ্যাঙ্করড sibling প্রমাণ

### 🛡️ `scripts/deploy/update_render_image.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 35 লাইন
- অপারেশনাল ডক-রেফ: docs/operations/BACKUP_RESTORE_AND_ROLLBACK.md

### ✂️ `scripts/devops/apply_patch.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 7 def, 0 class, 168 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### 🛡️ `scripts/devops/apply_tier_patch.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 4 def, 2 class, 272 লাইন
- অপারেশনাল ডক-রেফ: docs/master_docs/ARCH-02-SYSTEM_OVERVIEW_AND_FLOWS.md

### ✂️ `scripts/generate_isolation_markdown.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 176 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/generate_module_docs.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 1 def, 0 class, 131 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/inspect_rename_candidates.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 1 def, 0 class, 35 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/move_nonascii_root_plans.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 0 def, 0 class, 24 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/organize_external_plans.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 1 def, 0 class, 147 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/resource_collection/run_all_collectors.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 2 লাইন
- ঐতিহাসিক-ডক মেনশন (ক্যাপাবিলিটি-প্রমাণ নয়): docs/plans/features/repository_strict_file_hygiene_roadmap.md
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### 🧺 `scripts/scan_duplicate_plans.py` → **absorb-then-prune**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 0 def, 0 class, 63 লাইন
- manual-override: MODULE_21 doc-রেফারেন্সড সনাক্তকারী (duplicate-plan স্ক্যান) — কিন্তু f:\supremeai হার্ডকোডে অচল; MD5-dup + name/header-similarity লজিক scripts/supremeai_toolkit/plan_guard.py-এ পোর্টেবলভাবে পুনঃসৃষ্ট
