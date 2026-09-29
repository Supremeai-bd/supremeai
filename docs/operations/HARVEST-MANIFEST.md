# Harvest Manifest — group:foundation-closeout (seq:2)

> **তারিখ:** 2026-09-29 17:44 UTC · **ইঞ্জিন:** `scripts/supremeai_toolkit/harvest.py` · **roots:** scripts · **অডিট-বেস:** 405 ফাইল
> **Golden Rule:** ছাঁটাইয়ের আগে harvest — beneficial লজিক প্রথমে ক্যানোনিকাল মডিউলে, পরে খোসা।
> এই ম্যানিফেস্ট রায়-প্রমাণ মাত্র — নিজে কিছু ডিলিট করে না (read-only)।

## রায়-সারসংক্ষেপ (prune-candidate প্রার্থীদের গভীর পরীক্ষা)

| রায় | সংখ্যা | অর্থ |
| :--- | ---: | :--- |
| keep-operational | 7 | অপারেশনাল ডক/পরিবার-প্রমাণ — স্পর্শ নিষিদ্ধ |
| keep-canonical | 0 | repair-pairing/merge-হোম — রিপেয়ারে জীবন্ত হবে |
| absorb-then-prune | 0 | আগে toolkit-এ পুনঃসৃষ্ট, পরে ছাঁটাই |
| prune-after-harvest | 6 | প্রমাণিত অরফ্যান — ছাঁটাইযোগ্য |

## ফাইল-ভিত্তিক রায়

### ✂️ `scripts/ci/consolidate_env.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- non-portable: f:\supremeai হার্ডকোড (মূল ডেভ-মেশিনের ওয়ান-টাইম আর্টিফ্যাক্ট)
- content: 0 def, 0 class, 42 লাইন
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
- অপারেশনাল ডক-রেফ: docs/master_docs/ARCH-02-SYSTEM_OVERVIEW_AND_FLOWS.md, docs/master_docs/DEVOPS-01-PURE_CLOUD_INFRASTRUCTURE.md, docs/operations/BACKUP_RESTORE_AND_ROLLBACK.md, docs/operations/HARVEST-MANIFEST-foundation-closeout-seq2.md

### 🛡️ `scripts/deploy/update_render_env2.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 37 লাইন
- manual-override: DRY Phase 2-C3 render_client পরিবার — env-var ম্যানেজমেন্ট; runbook-অ্যাঙ্করড sibling প্রমাণ

### 🛡️ `scripts/deploy/update_render_image.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 35 লাইন
- অপারেশনাল ডক-রেফ: docs/operations/BACKUP_RESTORE_AND_ROLLBACK.md, docs/operations/HARVEST-MANIFEST-foundation-closeout-seq2.md

### 🛡️ `scripts/devops/apply_tier_patch.py` → **keep-operational**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 4 def, 2 class, 272 লাইন
- অপারেশনাল ডক-রেফ: docs/master_docs/ARCH-02-SYSTEM_OVERVIEW_AND_FLOWS.md, docs/operations/HARVEST-MANIFEST-foundation-closeout-seq2.md

### ✂️ `scripts/scratch_check_evidence.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 14 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/scratch_check_issues_status.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 31 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/scratch_check_prs.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 27 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/scratch_pr_files.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 19 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়

### ✂️ `scripts/scratch_pr_summary.py` → **prune-after-harvest**

- audit: prune-candidate (শূন্য রেফ + non-entry-point — harvest-check-এর পরেই কেবল ছাঁটাইযোগ্য)
- content: 0 def, 0 class, 37 লাইন
- শূন্য live-ref + অপারেশনাল-ডক-শূন্য + non-entry — Golden-Rule harvest-check সম্পন্ন, বেনিফিশিয়াল ইউনিক লজিক প্রমাণিত নয়
