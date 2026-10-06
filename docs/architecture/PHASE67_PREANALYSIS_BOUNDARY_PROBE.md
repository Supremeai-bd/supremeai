# Phase 6–7 Pre-Analysis: Evolution/Memory Boundary Probe (Verified)

> **বাংলা:** Roadmap §18 (Phase 6 — Evolution) ও Phase 7 (Memory) extraction-এর **পূর্ব-বিশ্লেষণ**।
> Core (Phase 5) ফ্রিজ থাকায় extraction নয় — এই ডকুমেন্ট verified dependency probe দিয়ে
> ভবিষ্যৎ extraction-এর পথ-নকশা তৈরি করে। পদ্ধতি: Phase 0-এর মতোই প্রমাণ-ভিত্তিক,
> monolith `main` @ `6bec525f`-এ import বিশ্লেষণ।

## ১. স্কোপ

| মডিউল | ফাইল | অবস্থান |
|---|---|---|
| Evolution | ১৩ | `backend/evolution/` |
| Memory | ১১ | `backend/memory/` |
| Core-অভ্যন্তরীণ fragment | ৪ | `backend/core/evolution/` (২) + `backend/core/memory/` (২) — §17-স্টাইল isolation টার্গেট |

সাথে পারিপার্শ্বিক: `frontend/src/components/memory` (UI), `apps/mission-control/.../api/memory` (operator API) — extraction-এর পরে এরা SDK contract দিয়ে যুক্ত হবে।

## ২. Forward Probe — evolution/memory কী import করে (verified counts)

| নির্ভরতা-শ্রেণি | Import সংখ্যা | বিস্তারিত |
|---|---|---|
| stdlib/external | ১৩৭ | chromadb, asyncio, sqlite3, supabase… |
| **`core.*`** | **৩৬** | নিচে ভাঙা |
| evolution-অভ্যন্তরীণ | ১৭ | নিজস্ব প্যাকেজ-অভ্যন্তর |
| memory-অভ্যন্তরীণ | ৭ | নিজস্ব প্যাকেজ-অভ্যন্তর |
| db/database | ২ | `database.supabase_client` |
| brain | ১ | `brain.model_router` (evolution-এ) |

### ২.১ core.* ভাঙা — **মূল আবিষ্কার**

| core মডিউল | ব্যবহার | শতাংশ |
|---|---|---|
| `core.logging_config` | **২৩** | **৬৪%** |
| `core.security.governance_policy` | ৩ | ৮% |
| `core.embeddings` | ৩ | ৮% |
| `core.self_evolution`, `core.utils.lazy_loader`, `core.mcp_audit`, `core.mcp_policy`, `core.llm.llm_gateway`, `core.ai_memory.repository`, `core.config` | ১ করে ×৭ | ২০% |

> **৬৪% কাপলিং শুধু logging!** — অর্থাৎ এটা আসল স্থাপত্যিক নির্ভরতা নয়, cross-cutting utility।
> logging চুক্তি (contract) আলাদা করলে বাকি আসল কাপলিং মাত্র ~১৩ import-এ নেমে আসে।

## ৩. Reverse Probe — কারা evolution/memory-কে consume করে

| মডিউল | Consumer জোন | তালিকা |
|---|---|---|
| memory | **৯** | api, brain, core, engine, external_agents, pipelines, services, tests, tools |
| evolution | ৫ | api, core, learning, services, tests |

> memory হলো **সবচেয়ে ব্যাপক-consumed মডিউল** — প্রায় প্রতিটি এজেন্ট-স্তর ছুঁয়েছে।
> contract ছাড়া এর extraction মানে ৯ জোনে ripple — তাই roadmap-এর contract-first নিয়ম এখানে সবচেয়ে জরুরি।

## ৪. External সার্ভিস-নির্ভরতা (per file)

| ফাইল | সার্ভিস |
|---|---|
| `memory/chromadb_store.py`, `episodic_memory.py`, `rag_pipeline.py`, `mcp_server.py` | ChromaDB |
| `memory/long_term_memory.py`, `supabase_store.py` | Supabase/Postgres |
| `memory/sliding_window.py`, `sqlite_store.py`, `supabase_store.py` | SQLite |
| `evolution/change_proposal.py` | Supabase |
| `memory/mcp_server.py` | ChromaDB+Supabase+**নিজস্ব MCP সার্ভার** — extraction-এ এটা পৃথক ডিপ্লয়েবল হতে পারে |

## ৫. রায় (Verdict) — এখনই extraction সম্ভব নয়, পথ পরিষ্কার

| গেট | অবস্থা |
|---|---|
| Core contracts স্থিতিশীল (§18 শর্ত) | ❌ Core ফ্রিজ (Phase 5 pending) |
| logging কাপলিং বিচ্ছিন্ন | ❌ ২৩ import — কিন্তু **mechanical fix** |
| Memory API contract SDK-তে | ❌ এখনো নেই — **আমরাই প্রথম ধাপ হিসেবে সংজ্ঞা দিতে পারি** |
| Internal fragment isolation (§17) | ❌ `core/evolution` + `core/memory` মনোলিথেই মিশে আছে |

## ৬. সুপারিশকৃত ক্রম (Phase 5-এর অপেক্ষায় চালানো যায় এমন)

1. **Logging ডিকাপলিং (সবচেয়ে সস্তা, সবচেয়ে বড় ফাইনা)** — `core.logging_config`-এর চুক্তি SDK/অবজারভেবিলিটি প্যাকেজে তুলে evolution/memory-কে সেটা পড়ানো → core-কাপলিং ৩৬→১৩
2. **Memory contract SDK-তে** — `memory/repository.py` interface-ই প্রাকৃতিক চুক্তি (episodic/long-term/sliding-window store interface); `supremeai-sdk`-র task-schemas-এ seed করা যায়
3. **Internal fragment isolation** — `core/evolution/` + `core/memory/`-কে `backend/evolution/`+`backend/memory/`-তে সরানো (monolith-অভ্যন্তরীণ move, কোনো রিপো-change নয়)
4. **Phase 5 Core স্থিত হলে** → Phase 6 evolution (৫ জোন consumer) → Phase 7 memory (৯ জোন — সবার শেষে, সবচেয়ে সাবধানে)

## ৭. Gate-এর জন্য প্রয়োজনীয় বেসলাইন (§17-ধারা)

- latency/cost/memory baseline: probe-এ নয় — extraction PR-এর আগে mission regression suite + বেসলাইন রান দরকার
- ChromaDB/Supabase নির্ভরতা → DR ও rollback প্ল্যান `FEDERATION_WIRING.md`-এ নিবন্ধিত হতে হবে

---

*প্রমাণ-পদ্ধতি: দ্বিমুখী regex import probe (forward + reverse), monolith @ `6bec525f`; স্ক্রিপ্ট-লগ PR-এ সংরক্ষিত। Phase 0-এর `PHASE0_BOUNDARY_CLASSIFICATION.md`-এর ভ্রাতৃ-ডকুমেন্ট।*
