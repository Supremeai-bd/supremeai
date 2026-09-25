# Capability-Surface Inventory (issue #1101)

> **এক source থেকে উত্তর:** কী আছে? কোনটা production-supported? কোনটা experimental?
> কোনটা অসম্পূর্ণ? কী প্রমাণ আছে? কোন issue মালিক?
>
> Machine-readable সত্য-ফাইল: [`docs/capability_inventory.json`](./capability_inventory.json)
> — hand-curated (bot-generated নয়); CI-তে `scripts/ci/validate_capability_inventory.py`
> যাচাই করে (ci-advanced-checks)।

## Classification (৫ স্তর)

| স্তর | সংজ্ঞা |
|---|---|
| 🟢 **Core** | Production-critical — ভাঙলে প্রোডাক্ট ভাঙে। টেস্ট + live caller + deploy evidence থাকতে হয়। |
| 🔵 **Supported** | Production-ready, optional কিন্তু বাস্তব ব্যবহার; টেস্ট আছে; degradation সহনীয়। |
| 🟠 **Experimental** | আসল কোড + caller আছে, কিন্তু চুক্তি অসম্পূর্ণ / flag-এর পেছনে / acceptance পূর্ণ নয়। |
| 🟡 **Deferred** | ইচ্ছাকৃত নিষ্ক্রিয় — milestone-এর অপেক্ষায়; owner issue-তে plan। |
| ⛔ **Deprecated** | অপসারণ-নির্ধারিত; নতুন বিনিয়োগ নিষেধ। |

## বর্তমান ছক (validator-যাচাইকৃত)

Core=10, Supported=8, Experimental=6, Deferred=2, Deprecated=0 — মোট **২৬ capability**।

বিস্তারিত (surface-paths, owner-issue, tests, evidence) JSON-এ দেখুন। সারসংক্ষেপ:

- **Core (10):** auth/api-keys · chat · llm-gateway · agents · admin-console ·
  billing/wallet · browser-automation · cache · observability/health · security/vault
- **Supported (8):** MCP-audit-chain (#928) · MCP hub/marketplace · memory ·
  crawler · integrations · HITL/approvals · automation · i18n
- **Experimental (6):** mesh-core (#943) · self-evolution (#1096) · BYOC ·
  IDE-trio · learning/behavioral · voice
- **Deferred (2):** mesh-telegram (#942) · mesh-playwright-vault (#943)
- **Deprecated (0):** shim পরিষ্কার (#1159/#1165) শেষ — বর্তমানে শূন্য

## Duplicate / Overlap খুঁজে পাওয়া ফাঁক (নতুন abstraction-এর আগে পড়ুন)

1. **MCP server ×৩** — `tools/mcp/mcp_server.py` (stdio KG), `memory/mcp_server.py`
   (memory KG stdio), REST hub (`mcp_hub.py`) → #1115 (Phase 3) consolidation।
2. **Admin surface বিচ্ছিন্ন** — `admin.py` / `admin_v1.py` / `admin_routes.py` /
   `admin_auth.py` / `admin_dashboard/` → #1115 scope।
3. **i18n বনাম localization** — দুটি সমান্তরাল namespace → #1115 scope।
4. **MODULES_LIST.md duplicate** — repo root + `docs/reference/` → single
   canonical source দরকার (#1213 এ truth-sync দেওয়া)।
5. **Retired:** error_handler/ssrf_protection shims (#1159), error_bus sweep
   (#1165) — আর কোনো deprecated shim core/-তে নেই।

## Review protocol (কীভাবে এটা drift ঠেকায়)

- **নতুন feature PR:** capability entry যোগ/আপডেট করতে হবে (classification +
  surfaces + owner_issue + evidence) — validator CI-তে মিথ্যা/মিসিং entry ধরে।
- **নতুন abstraction-এর আগে:** এই ফাইলে duplicate/overlap section দেখুন —
  দ্বিতীয় implementation শুরু করার আগে প্রমাণ দিন যে বিদ্যমান capability যথেষ্ট নয়।
- **Experimental isolation:** experimental capability core-এর উপর চাপ না বাড়ায়
  তার নিজের boundary-তে থাকে; Core-তে উন্নীত হতে হলে tests + evidence +
  owner-issue পূরণ করতে হয়।

## রক্ষণাবেক্ষণ

- ফাইল: `docs/capability_inventory.json` (একটাই; hand-curated)
- যাচাই: `python scripts/ci/validate_capability_inventory.py` (exit 0 হতে হবে)
- surface-paths ডিস্কে না থাকলে validator fail করে — মৃত দাবি অসম্ভব
