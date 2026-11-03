# SupremeAI Script Consolidation & Reusability Master Spec

> **ইস্যু ট্র্যাকার:** [Issue #2403](https://github.com/SaifulHaqueNiloy/supremeai/issues/2403) — Reusability Audit, Deep Dead-Code Pruning & 497 Scripts Intelligent Re-creation  
> **সংবিধান রুল:** Rules v2.7 · Protocol 14 (DRY 3-Pipeline Law) & Golden Rule (No Deletion Before Reusability Audit)  
> **টুলস:** `scripts/supremeai_toolkit/` (Unified CLI Dispatcher)  
> **সর্বশেষ আপডেট:** 2026-09-29  

---

## ১. গোল্ডেন রুল (The Absolute Golden Law)

> **"Clean up-এর আগে Reusability Check — beneficial কিছু কোনো অবস্থাতেই ডিলিট করা যাবে না।"**  
> কোনো ফাইল বা স্ক্রিপ্ট ছাঁটাই করার পূর্বে দেখতে হবে এর ভেতরে এমন কোনো দরকারি লজিক, হেল্পার বা ফিচার আছে কিনা যা ভবিষ্যতে কাজে লাগবে। দরকারী লজিক থাকলে তা ক্যানোনিকাল মডিউলে সংরক্ষণ (Harvest) করতে হবে, তারপরই কেবল অপ্রয়োজনীয় খোসা ছাঁটাই করা যাবে।

---

## ২. বর্তমান লাইভ ইনভেন্টরি ও অডিট স্ট্যাটাস (SSOT)

আমাদের `scripts/supremeai_toolkit/` অডিট ও হারভেস্ট ইঞ্জিনের সর্বশেষ লাইভ স্ক্যান ফলাফল:

| ক্যাটাগরি | সংখ্যা | বিবরণ ও নীতি |
| :--- | :---: | :--- |
| **Keep-Canonical** | ২৫৬টি | লাইভ GitHub Workflows এবং ব্যাকএন্ড কোডে সরাসরি রেফারেন্সড — **স্পর্শ সম্পূর্ণ নিষিদ্ধ**। |
| **Keep-Structural** | ৩৭টি | `__init__.py` প্যাকেজ মার্কার — পাইথন ইমপোর্ট সিস্টেম ও পাথ রেজোলিউশন রক্ষা করে। |
| **Keep-Tested** | ১৪টি | `test_*.py` — Pytest discovery এবং Test Guard নীতি রক্ষা করে। |
| **Keep-Operational** | ৭০টি | অপারেশনাল রানবুক ও ডেভপস টুলস (যেমন: `cleanup_stale_branches.py`, `delete_vault_stale_keys.py`) — অপারেটর ও টেকনিশিয়ানরা সরাসরি চালান। |
| **Absorb-Candidates** | ১৫টি | পোর্টেবল এবং ইউনিক লজিক সম্পন্ন স্ক্রিপ্ট — এগুলোকে `scripts/supremeai_toolkit/`-এ সাবকমান্ড হিসেবে একীভূত করা হবে। |
| **Stale-Review** | ৭টি | পুরনো বা ডিপ্রিকেটেড স্ক্রিপ্ট — হারভেস্ট অডিট শেষে প্রুনিংয়ের জন্য চিহ্নিত। |
| **Prune-After-Harvest** | **০টি** | প্রমাণিত ৬টি ডেড ও নন-পোর্টেবল স্ক্রিপ্ট ইতিমধ্যে অপসারিত। |
| **মোট লাইভ স্ক্রিপ্ট** | **৩৯৯টি** | মূল ৪৯৭টি থেকে কমিয়ে ৩৯৯টিতে নামিয়ে আনা হয়েছে (**৯৮টি স্প্রল/অরফ্যান মুক্ত**)। |

---

## ৩. ইন্টেলিজেন্ট সেন্ট্রাল টুলে একীভূতকরণ রোডম্যাপ (SupremeAI Toolkit)

বিচ্ছিন্ন স্ক্রিপ্ট আলাদা রাখার বদলে সেগুলোকে একক সেন্ট্রাল CLI `python -m scripts.supremeai_toolkit <command>`-এর অধীনে আনা হচ্ছে:

```
scripts/supremeai_toolkit/
├── __main__.py          # মূল প্রবেশদ্বার (CLI Entrypoint)
├── cli.py               # আর্গুমেন্ট ডিসপ্যাচার ও সাবকমান্ড হ্যান্ডলার
├── reusability_audit.py # রিউজেবিলিটি অডিট ইঞ্জিন (audit সাবকমান্ড)
├── harvest.py           # হারভেস্ট ডিসিশন ইঞ্জিন (harvest সাবকমান্ড)
├── plan_guard.py        # ডক ও প্ল্যান স্প্রল গার্ড (plan-guard সাবকমান্ড)
├── standalone_check.py  # রান-ভ্যালু ও অপারেশনাল চেকার (standalone সাবকমান্ড)
└── ops_sync.py          # অপারেশনাল ট্রুথ ও ইনভেন্টরি সিঙ্ক (পরবর্তী ফেজ)
```

### ১৫টি Absorb-Candidate ফাইল ও মার্জিং লক্ষ্য:
1. `scripts/operations/sync_operational_truth.py` (৪৬৯ লাইন) $\rightarrow$ `toolkit/ops_sync.py`
2. `scripts/ci/sprawl_guard.py` $\rightarrow$ `toolkit/sprawl_guard.py`
3. `scripts/ci/smart_priority_merger.py` $\rightarrow$ `toolkit/merger.py`
4. অন্যান্য আইসোলেটেড ভ্যালিডেশন স্ক্রিপ্ট $\rightarrow$ `toolkit/validators/`

---

## ৪. দ্য ৪-অটোমেটেড কন্টিনিউয়াস লুপ (Continuous Maintenance System)

ভবিষ্যতে যেন আর কখনো স্ক্রিপ্ট স্প্রল বা ড্রিফট না ঘটে, তার জন্য ৪টি স্বয়ংক্রিয় লুপ কার্যকর:

1. **Loop 1: Script Sprawl Guard (`scripts/ci/sprawl_guard.py`)**
   - PR Gate-এ চলে। `scripts/` রুটে অনুমোদন ছাড়া কোনো নতুন স্ক্রিপ্ট যুক্ত হলে PR ব্লক হবে।
2. **Loop 2: SSOT & Doc-Drift Guard (`scripts/generate_script_index.py --check`)**
   - PR Gate-এ চলে। `scripts/_INDEX.md` কোডের সাথে শতভাগ সিঙ্কড থাকতে হবে।
3. **Loop 3: Governance-First Auto-Merger (`scripts/ci/smart_priority_merger.py`)**
   - ৫+ পিআর হলে বা ট্রেনের মাধ্যমে টেস্ট গ্রিন ও সুরক্ষিত পিআরগুলো স্বয়ংক্রিয়ভাবে ক্রমানুসারে মার্জ করে।
4. **Loop 4: Automated Janitor (`scripts/ci/purge_stale_workflow_runs.py`)**
   - `nightly-ops.yml`-এ প্রতি রাতে স্বয়ংক্রিয়ভাবে অচল শিডিউল রান ও স্টেল লগ পরিষ্কার রাখে।

---

## ৫. ৩-স্তর ভেরিফিকেশন চুক্তি (Verification Contract)

প্রতিটি পরিবর্তনের আগে ও পরে ৩টি যাচাই বাধ্যতামূলক:
1. **Reflection Check (Sprawl Guard):** `python scripts/ci/sprawl_guard.py --check-all`
2. **Index Freshness Check:** `python scripts/generate_script_index.py --check`
3. **Fast Boot Smoke Test:** `python -c "import backend.main; print('[OK] Boot smoke passed')"`
