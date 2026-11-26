# SupremeAI Documentation Index & Archive SSOT

## 🧭 Living Backlog (SSOT — 2026-11-26)

> বাংলা মন্তব্য: এই টেবিলই একমাত্র "current" ব্যাকলগ — নিচের পুরনো plan/audit ডকগুলো ARCHIVED
> হিসেবে চিহ্নিত (audit B6)। স্টেটাস এখানে আপডেট হবে; পুরনো ফাইলের কনটেন্ট ইতিহাস হিসেবে রাখা।

| Item | বিবরণ | স্টেটাস | SSOT ref |
|------|--------|---------|----------|
| M01–M07 | MASTER_SIMPLIFICATION_PLAN আইটেম (rate-limit census, memory SSOT, guard registry…) | **tracked** | `docs/MASTER_SIMPLIFICATION_PLAN.md` (ARCHIVED banner দেখো) |
| B1–B8 | 2026-11-26 ডিপ অডিট — de-over-engineering (guard registry, workflow split, health canonical…) | **tracked** | GitHub issue (audit backlog) |
| A1–A7 | Smart automation (session_boot, auto_doctor wire, tracker freshness) | **partial live** | `scripts/agents/session_boot.sh`, `.github/workflows/unified-pipeline.yml`, `scripts/ci/tracker_freshness.py` |

---

This repository (`Supremeai-bd/supremeai`) maintains an ultra-light, active documentation footprint. Historical planning documents, legacy audits, satellite mirrors, and ephemeral agent run receipts are archived in the dedicated cold-storage archive repository.

---

## 🗄️ Historical Archive Repository

All archived documentation is preserved with full git history in:
👉 **[Supremeai-bd/supremeai-archive](https://github.com/Supremeai-bd/supremeai-archive)**

### What lives in `supremeai-archive`:
- **Historical Worklogs & Transits:** `docs/bridge/` (Agent execution receipts and bridge orders)
- **Historical ADRs & Audits:** `adrs/`, `docs/reports/`, `docs/audit_reports/`
- **Legacy Roadmaps & Plans:** `docs/plans/`, `legacy-specs/`, `roadmap-snapshots/` (e.g. `FRONTEND_PERFECTION_PLAN.md`, `SOCIAL_MEDIA_AUTOMATION_PLAN.md`, `SUPREMEAI_DESKTOP_ANDROID_PLAN.md`, `ARCHITECTURAL_COMPARISON_AND_ADOPTION_BLUEPRINT.md`)
- **Retired Satellite Snapshots:** `satellites/` (`supremeai-core`, `supremeai-api`, `supremeai-browser`, `supremeai-vscode`)
- **Blueprints & Research:** `docs/research/`

---

## 📚 Active Monorepo Documentation (SSOT)

The active documents in this repository govern live production operations, architecture, and autonomous agent loops. The simplification plan records the reviewed local baseline, verified findings, open operational questions and a phased, evidence-led backlog; it does not claim the whole suite or production services passed verification.

| Document | Purpose |
|---|---|
| [`AGENTS.md`](../AGENTS.md) | Universal Agent Constitution & the 5 Universal Invariants |
| [`docs/AGENT_OPERATING_SYSTEM.md`](AGENT_OPERATING_SYSTEM.md) | Multi-Agent Operating System & verification ladder |
| [`docs/AGENT_LOOP_SPEC.md`](AGENT_LOOP_SPEC.md) | Continuous loop contract and dispatch roles |
| [`docs/AUTONOMY_LOOP_CONTRACT.md`](AUTONOMY_LOOP_CONTRACT.md) | Autonomy invariants and permission rules |
| [`docs/LOOP_ALIGNMENT.md`](LOOP_ALIGNMENT.md) | Agent loop alignment and task claiming SSOT |
| [`docs/ECOSYSTEM_MAP.md`](../ECOSYSTEM_MAP.md) | Complete capability and architectural ecosystem map |
| [`docs/CAPABILITY_REALITY_MATRIX.md`](CAPABILITY_REALITY_MATRIX.md) | What a user can actually ask for today vs. what is only advertised — chat, voice, browser automation, scraping |
| [`docs/specs/`](specs/) | Active feature specifications (Spec-Driven Development) |
| [`.agents/`](../.agents/) | Executable agent skills, workflows, and prompts |

## Project simplification

- [Master Simplification & Quality Plan](MASTER_SIMPLIFICATION_PLAN.md) — final implementation roadmap, decision gates, and the single M01–M07 queue.
- [Earlier repo audit (বাংলা)](PROJECT_SIMPLIFICATION_MASTER_PLAN.md) — supporting inventory, wiring, and checks for the `aa11e0b` snapshot.

