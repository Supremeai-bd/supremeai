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
| `DOCUMENTATION_MASTER_INDEX.md` | ঐতিহাসিক মাস্টার ইনডেক্স (এই ফাইলের পূর্বসূরি) |

## ৪. Archive & Recovery

- **Archive:** `archives/legacy-docs-2026-09-28.tar.gz` — তালিকা: `tar -tzf archives/legacy-docs-2026-09-28.tar.gz`
- **Recovery:** `tar -xzf archives/legacy-docs-2026-09-28.tar.gz` (repo root থেকে) অথবা `git log --follow -- docs/plans/<name>.md`
- **নতুন প্ল্যান/অডিট কোথায়?** নতুন প্ল্যান GitHub Issue-তে (planner lane); অডিট রিপোর্ট `docs/audit_reports/`-এ টুলিং-নির্ধারিত নামে। docs/-তে যত্রতত্র `.md` নয়।

---
_এই ইনডেক্স docs/-এর একমাত্র প্রবেশদ্বার — নতুন ক্যানোনিকাল ডক যোগ হলে এখানে রেজিস্টার করো। (#2450)_
