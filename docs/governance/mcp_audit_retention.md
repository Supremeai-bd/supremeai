# MCP Audit Retention & Tamper-Evidence Policy (issue #928)

> বাংলা: MCP Tower gap-4 — per-agent verified audit-এর চালুকরণ, সংরক্ষণ ও
> অখণ্ডতা-নীতি। Canonical implementation: `backend/core/mcp_audit_chain.py`
> + `backend/models/mcp_audit_event.py` + alembic `u8v9w0x1y2z3`।

## ১. কী রেকর্ড হয়

প্রতিটি MCP tool call (read + write) — middleware স্তরে (`tools/mcp/mcp_server.py`
`handle_call_tool`-এর finally) auto-instrument হয়, আলাদা করে কেউ লিখতে ভুলবে না:

```
{event_id, ts, tenant_id, agent_id, client_role, provider, server,
 tool, args_hash (sha256), result_status, result_ref, error,
 hitl: {required, approver}, prev_hash, entry_hash}
```

- **args কখনো কাঁচা সংরক্ষণ হয় না** — শুধু `args_hash = sha256(canonical_json(args))`
  (secrets লিক-প্রতিরোধ)।
- `result_status ∈ {ok, error, policy_blocked, failed}`।

## ২. Hash chain (tamper-evident)

- Tenant-scope চেইন: `entry_hash = sha256(prev_hash + canonical_json(payload))`
- প্রথম event: `prev_hash = ""`
- চেইন ভাঙা ধরার tool: MCP tool **`audit_verify`** (টেবিলের উপরে হাত চালালে —
  UPDATE/DELETE/insert-out-of-order — `entry_hash_mismatch` /
  `prev_hash_link_broken` রিপোর্ট হয়)।

## ৩. Retention policy — **৯০ দিন**

- `mcp_audit_events` রেকর্ড **৯০ দিন** সংরক্ষিত থাকবে।
- Purge শুধু পুরনো রেকর্ডে (ts < now − 90d), নতুন chain tip অক্ষত রেখে।
  পুরনো প্রান্ত কাটা chain-এর শুরু ছোট হয়ে যায় — `verify()` সবসময়
  retention window-এর মধ্যেই চালানো হয় (`since` param), তাই এটি নিরাপদ।
- Prod-এ pg_cron দিয়ে nightly purge (owner Supabase-এ চালু করবেন):

```sql
select cron.schedule(
  'mcp-audit-retention-90d', '17 3 * * *',
  $$delete from mcp_audit_events where ts < now() - interval '90 days'$$
);
```

## ৪. Append-only enforcement (Supabase RLS)

application স্তর কখনো UPDATE/DELETE ইস্যু করে না; DB-স্তরেও বন্ধ করতে
Supabase SQL editor-এ (service role দিয়ে) একবার চালান:

```sql
-- ৪.১ RLS চালু + নিজের চূড়ান্ত নীতি
alter table mcp_audit_events enable row level security;

-- ৪.২ INSERT শুধু service_role (app) — anon/authenticated নয়
create policy mcp_audit_insert_service_only on mcp_audit_events
  for insert to service_role with check (true);

-- ৪.৩ SELECT শুধু service_role (audit_query tool app-এর ভিতরে দিয়েই চলে)
create policy mcp_audit_select_service_only on mcp_audit_events
  for select to service_role using (true);

-- ৪.৪ UPDATE/DELETE — কারো জন্যই কোনো policy নেই ⇒ ডিফল্টভাবে deny (RLS fail-closed)
--     (নিশ্চিত করতে স্পষ্ট revoke):
revoke update, delete on mcp_audit_events from anon, authenticated;
```

> ফল: টেবিল **append-only** — update/delete কেউ পারবে না (service_role-ও নয়,
> কারণ RLS-এ কোনো update/delete policy নেই)। হ্যাঁ, এর মানে ভুল data ঢুকলে
> সেটা থেকে যাবে — সেটাই তামার-সিল; ভুল ঢোকানোর ঘটনাও `audit_verify`/হিসাবে
> দৃশ্যমান থাকবে।

## ৫. Anomaly rules (live)

`audit_verify`-এর সাথে প্রতিবার চলে:

| Rule | থ্রেশহোল্ড | Action |
|---|---|---|
| `failure_rate_spike` | শেষ ২০ event-এ এক agent-এর ≥৫০% `error`/`policy_blocked` | `needs-human-review` flag |

ভবিষ্যৎ candidates (এই PR-এর scope নয়): off-hours burst, protected-path touch,
per-tenant volume spike।

## ৬. Acceptance mapping (issue #928)

- [x] Audit middleware: ১০টি নমুনা tool call → ১০টি chained event — `test_mcp_audit_chain.py::test_ten_chained_events`
- [x] `audit_verify` tamper detect — `::test_tamper_detection`
- [x] `audit_query` per-agent report <1s — `::test_query_per_agent_under_1s`
- [x] Anomaly rule ≥১ live — `::test_anomaly_failure_rate_rule`
- [x] Retention policy doc — এই ফাইল (§৩)
