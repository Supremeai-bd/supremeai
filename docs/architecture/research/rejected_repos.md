# Rejected Repos — Rationale Record (issue #4063)

> **Purpose:** Document repos evaluated and explicitly rejected, with rationale. Prevents future re-auditing of the same repos.
>
> **Rule 4 (Evidence Before Adoption):** Every rejection has documented evidence.

---

## Rejected Repos

### anthropic-tools (REJECT — #4063)

| Field | Value |
|---|---|
| **Category** | Tooling |
| **Issue** | #4063 |
| **Decision** | REJECT |
| **Date** | 2026-10-06 |
| **Reason** | Archived + deprecated |

**Evidence:** The `anthropic-tools` repository is archived on GitHub and marked as deprecated. No maintenance, no updates, no community support. Using archived/deprecated repos violates Rule 4 (Evidence Before Adoption) — no evidence of reliability or future support.

**Do NOT re-audit:** This decision is final. If a future task needs Anthropic tool-use capabilities, use the native Anthropic SDK directly (already integrated via `backend/core/llm/providers/cloud_adapter.py` with prompt caching per PLAN-001).

---

### Appwrite (REJECT — Roadmap v2 §2.2 row #19)

| Field | Value |
|---|---|
| **Category** | Backend-as-a-Service (BaaS) |
| **Decision** | REJECT |
| **Reason** | Over-engineering risk |

**Evidence:** SupremeAI already has a comprehensive backend stack (FastAPI + Supabase + Firebase + Redis). Adding Appwrite would introduce a competing BaaS layer with overlapping capabilities (auth, database, file storage, real-time). This violates Rule 5 (Consolidation Over Expansion) — "how much capability improved per added complexity?" Answer: zero improvement, doubled complexity.

---

### HackProduct (REJECT — Roadmap v2 §2.2 row #20)

| Field | Value |
|---|---|
| **Category** | Productivity |
| **Decision** | REJECT (read-only) |
| **Reason** | Weak recommendation |

**Evidence:** HackProduct was reviewed during the ecosystem analysis. The recommendation was weak — no clear capability gap it fills that SupremeAI's native system doesn't already cover. Reading the repo for ideas is acceptable; adopting it is not.

---

## Cross-References

- **Capability Inventory:** `docs/architecture/CAPABILITY_INVENTORY.md` §8 (External Repos Analyzed)
- **Machine-readable inventory:** `docs/architecture/inventory.yaml` → `external_repos` (tier: rejected)
- **Roadmap v2 §2.2:** `docs/architecture/ECOSYSTEM_INTELLIGENCE_ROADMAP.md` — Integration Matrix
- **Roadmap v2 Rule 4:** Evidence Before Adoption
- **Retired adapters:** `docs/architecture/retired_adapters.md` (different scope — adapters that were integrated then retired)

---

*Bengali note (AGENTS.md Rule #6): এই ডক প্রত্যাখ্যাত repo-গুলোর rationale নথিভুক্ত করে — anthropic-tools (archived), Appwrite (over-engineering), HackProduct (weak)। ভবিষ্যতে এই repo-গুলো পুনরায় audit করবেন না — সিদ্ধান্ত চূড়ান্ত। Evidence Before Adoption (Rule 4) অনুসারে প্রতিটি প্রত্যাখ্যানের প্রমাণ নথিভুক্ত।*
