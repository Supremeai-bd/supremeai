# 📚 SupremeAI Documentation Index (Single Canonical Index)

> 🇧🇩 **দর্শন:** "GitHub Issues as Live Operational Truth (Static Docs as Minimal Archival Backup)" — সচল সত্য GitHub Issues-এ; docs/-এ শুধু ক্যানোনিকাল স্পেক।
>
> **Zero-Garbage Guard:** `docs/`-এ নতুন `.md` শুধু অনুমোদিত জায়গায় (allowlist: `.github/constitution/rules.yml` → `docs_garbage_policy`) — গেট: `gates.py docs_garbage` (#2450, 2026-09-28)।
>
> **লিগ্যাসি আর্কাইভ:** পুরনো ৩১০টি ফাইল (plans ১৫৮ + plan-network ৫২ + archive ৯৮ + অন্যান্য) → `archives/legacy-docs-2026-09-28.tar.gz` (git history-তে সবসময় পুনরুদ্ধারযোগ্য)।

---

## ১. Master Specs (ক্যানোনিকাল মাস্টার স্পেক)

`docs/master_docs/` — ২৩টি ক্যানোনিকাল স্পেক + `AGENT_SLOT_REGISTRY.yaml`:

| Prefix | বিষয় |
|---|---|
| `ARCH-*` | সিস্টেম আর্কিটেকচার, constitution, roadmap, gap-analysis |
| `AIBRAIN-*` | এজেন্ট সিস্টেম মাস্টার প্ল্যান |
| `BACKEND-*` | API রেফারেন্স ও মাইক্রোসার্ভিস চুক্তি |
| `FRONTEND-*` | ডিজাইন সিস্টেম ও টোকেন |
| `INTEG-*` | MCP ইন্টিগ্রেশন, IDE এক্সটেনশন |
| `OPS-*` | টেস্টিং স্ট্র্যাটেজি, রানবুক, PR-Helper/Developer-Agent লাইফসাইকেল, জানিটর |
| `SEC-*` | ক্যাটাগরি সিকিউরিটি ম্যাট্রিক্স |
| `DEVOPS-*` | ক্লাউড ইনফ্রাস্ট্রাকচার |
| `SCRIPTS_CONSOLIDATION_MASTER.md` | স্ক্রিপ্ট কনসোলিডেশন, রিউজেবিলিটি অডিট ও Toolkit মাস্টার স্পেক (#2403) |

## ২. Active Directories (সচল টুলিং-সংযুক্ত — স্পর্শ করার আগে ref-audit করো)

| ডিরেক্টরি | কেন active |
|---|---|
| `docs/agents/` | এজেন্ট চার্টার, রোল, `ISSUE_PRIORITY_POLICY.md` (priority-queue লেজার রেফারেন্স) |
| `docs/architecture/` | `ARCH-LIVING-PIPELINE-01.md` — AGENTS.md §12-এর canon spec |
| `docs/plans/` | শুধু `ARCH-LIVING-PIPELINE-01-IMPL.md` (AGENTS.md §12 roadmap) + `lint_plans.py`-এর live target |
| `docs/governance/` | গভর্নেন্স টুলিং-সংযুক্ত |
| `docs/audit_reports/`, `docs/audits/` | `sync_modules_list.py`, `audit_module_wiring.py`, `sync_operational_truth.py`-এর write-target — পরবর্তী per-file ref-audit স্লাইসে prune হবে |
| `docs/reference/`, `docs/security/`, `docs/operations/`, ... | per-file ref-audit বাকি — ধাপে ধাপে মিনিমাইজ হবে |

## ৩. Top-Level Canonical Docs

| ফাইল | বিষয় |
|---|---|
| `SECRETS_OPERATIONS.md` | Infisical অপারেশন — raw-path API চুক্তি (#434 workaround) |
| `ROADMAP.md` | লাইভ প্রায়োরিটি রোডম্যাপ |
| `SKIPPED_TESTS.md` | টেস্ট স্কিপ রেজিস্ট্রি (Test Guard-এর সঙ্গী) |
| `CAPABILITY_INVENTORY.md` | সক্ষমতা ইনভেন্টরি |
| `governance/DOCUMENTATION_MIGRATION_PLAN.md` | মাস্টার ডকুমেন্টেশন অডিট, এক্সটার্নাল মাইগ্রেশন ও রিটেনশন প্ল্যান |

## ৪. Archive & Recovery

- **Legacy Archives:** 
  - `archives/legacy-docs-2026-09-28.tar.gz` — ৩১০টি পুরানো প্ল্যান ও রেফারেন্স
  - `archives/legacy-docs-2026-09-29.tar.gz` — ১৫টি ঐতিহাসিক অডিট, ফিক্স লগ ও সাময়িক রিপোর্ট (TelDrive ব্যাকআপ)
  - `archives/external-docs-export-2026-09-29.tar.gz` — ১২টি এক্সটার্নাল মাইগ্রেশন ডকুমেন্ট (Notion / TelDrive ব্যাকআপ)
  - `archives/legacy-docs-phase2-2026-09-29.tar.gz` — ১৪টি ঐতিহাসিক অডিট, মাস্টার ইনডেক্স ও টেস্ট প্ল্যান (TelDrive ব্যাকআপ)
- **Recovery:** `tar -xzf archives/legacy-docs-<date>.tar.gz` (repo root থেকে) অথবা `git log --follow -- <path>`
- **নতুন প্ল্যান/অডিট কোথায়?** নতুন প্ল্যান GitHub Issue-তে (planner lane); অডিট রিপোর্ট `docs/audit_reports/`-এ টুলিং-নির্ধারিত নামে। docs/-তে যত্রতত্র `.md` নয়।

### Pruned Module Recovery Notes (#2470 — §9 zero-capability-loss)

- **`backend/core/type_sync_bus.py`** (২৯৯ লাইন, 2026-09-29 prune): NATS→type-generator bridge (`types.sync`/`types.drift_detected` চ্যানেল)। বাংলা মন্তব্য: প্রমাণিত ডেড মডিউল — রিপো-ব্যাপী শূন্য importer, `nats` কোনো requirements-এ নেই (guarded import), boot/lifespan-এ wire নেই, এবং টাইপ-জেনারেশনের কোনো স্বয়ংক্রিয় ট্রিগার নেই। ড্রিফট-ডিটেকশন ক্ষমতা `scripts/advanced_analysis/pydantic_schema_consistency_checker.py --ts-check`-এ বিদ্যমান — শূন্য ক্ষমতা-ক্ষতি। পুনরুদ্ধার: `git log --follow -- backend/core/type_sync_bus.py`

---
_এই ইনডেক্স docs/-এর একমাত্র প্রবেশদ্বার — নতুন ক্যানোনিকাল ডক যোগ হলে এখানে রেজিস্টার করো। (#2450)_
