import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore } from "./src/policy/auth.context.js";
import { defaultClientScopes } from "./src/policy/client-registry.js";
import {
  TOWER_MASTER_TOOLS,
  TowerToolCatalog,
  registerTowerCatalogTools,
} from "./src/tools/tower.catalog.js";

/**
 * Tower master-tool contract tests (tower_catalog / tower_describe / tower_invoke).
 *
 * বাংলা মন্তব্য: যাচাই হয় —
 *   ১. catalog: query/domain/risk ফিল্টার + pagination + RBAC-ফিল্টারড দৃশ্যমানতা
 *   ২. describe: লাইভ রেজিস্ট্রেশন থেকেই schema প্রতিফলিত হয় (drift অসম্ভব)
 *   ৩. invoke: টার্গেটের নিজের zod স্কিমা দিয়ে ভ্যালিডেশন — ব্যর্থ হলে হ্যান্ডলার
 *      কখনো চলে না (ফ্যান্টম সফলতা নেই); সফল হলে টার্গেটের আসল উত্তর হুবহু ফেরে
 *   ৪. destructive টার্গেটে confirm ছাড়া invoke প্রত্যাখ্যাত
 *   ৫. meta-tool recursion বন্ধ
 *   ৬. e2e: আসল McpServer + InMemoryTransport ক্লায়েন্টের ওপর দিয়ে তিনটি টুলই
 *
 * Rule #64: সব কিছু mocked — কোনো রিয়েল Render/Supabase/Redis কল নেই।
 */

const admin = { role: "admin" as const, accessMode: "admin" as const, authenticated: true, scopes: ["*"] };
const guest = { role: "viewer" as const, accessMode: "public_viewer" as const, authenticated: false, scopes: [] };

function buildCatalog() {
  const catalog = new TowerToolCatalog();
  const calls: Array<{ tool: string; args: unknown }> = [];

  catalog.record(
    {
      name: "render_service_health",
      description: "Return live Render service health for one service id. Read-only.",
      shape: { serviceId: z.string().describe("Render Service ID") },
      annotations: { readOnlyHint: true },
    },
    (args) => {
      calls.push({ tool: "render_service_health", args });
      return { content: [{ type: "text", text: JSON.stringify({ live: true, status: "ok", ...(args as object) }) }] };
    },
  );

  catalog.record(
    {
      name: "github_list_prs",
      description: "List pull requests. Read-only.",
      shape: { state: z.enum(["open", "closed"]).optional() },
      annotations: { readOnlyHint: true },
    },
    (args) => {
      calls.push({ tool: "github_list_prs", args });
      return { content: [{ type: "text", text: JSON.stringify({ live: true, prs: [] }) }] };
    },
  );

  catalog.record(
    {
      name: "action_redis_flush",
      description: "Flush Redis. Destructive.",
      shape: { prefix: z.string().optional(), confirm: z.boolean().optional() },
      annotations: { destructiveHint: true, readOnlyHint: false },
    },
    (args) => {
      calls.push({ tool: "action_redis_flush", args });
      return { content: [{ type: "text", text: JSON.stringify({ flushed: true }) }] };
    },
  );

  // A tool the caller cannot call must not be discoverable either.
  catalog.record(
    {
      name: "infisical_vault_keys",
      description: "Secret-class tool. Admin only.",
      shape: { path: z.string() },
      annotations: { readOnlyHint: true },
    },
    () => ({ content: [{ type: "text", text: "SECRET" }] }),
  );

  return { catalog, calls };
}

// ─── ১. catalog search: filter + pagination ────────────────────────────────
await RequestContextStore.run(admin, async () => {
  const { catalog } = buildCatalog();
  assert.equal(catalog.size, 4, "all registrations are recorded");

  const page = catalog.search({});
  assert.ok(page.total >= 3, "authorized tools are listed");
  assert.ok(page.tools.every((tool) => ["read", "write", "destructive"].includes(tool.risk)));

  const renderOnly = catalog.search({ query: "render" });
  assert.deepEqual(renderOnly.tools.map((t) => t.name), ["render_service_health"]);

  const byDomain = catalog.search({ domain: "github" });
  assert.deepEqual(byDomain.tools.map((t) => t.name), ["github_list_prs"]);

  const destructive = catalog.search({ risk: "destructive" });
  assert.deepEqual(destructive.tools.map((t) => t.name), ["action_redis_flush"]);

  const paged = catalog.search({ limit: 1 });
  assert.equal(paged.returned, 1);
  assert.ok(paged.nextCursor, "pagination cursor emitted when more results exist");
  const second = catalog.search({ limit: 1, cursor: paged.nextCursor });
  assert.notEqual(second.tools[0]?.name, paged.tools[0]?.name, "cursor advances");

  const noMatch = catalog.search({ query: "definitely-not-a-tool" });
  assert.equal(noMatch.total, 0);
});

// ─── ২. describe reflects the live schema ──────────────────────────────────
await RequestContextStore.run(admin, async () => {
  const { catalog } = buildCatalog();
  const described = catalog.describe("render_service_health");
  assert.equal(described.ok, true);
  if (described.ok) {
    const tool = described.tool as any;
    assert.equal(tool.risk, "read");
    assert.equal(tool.parameters.serviceId.required, true);
    assert.equal(tool.parameters.serviceId.description, "Render Service ID");
    assert.match(tool.call, /tower_invoke/);
  }
  const optionalParam: any = catalog.describe("github_list_prs");
  assert.equal(optionalParam.ok, true);
  assert.equal(optionalParam.tool.parameters.state.required, false, "optional() reflected as required:false");
});

// ─── ৩. invoke: validation-first, verbatim passthrough ────────────────────
await RequestContextStore.run(admin, async () => {
  const { catalog, calls } = buildCatalog();

  const ok = (await catalog.invoke("render_service_health", { serviceId: "srv-123" }, {})) as any;
  assert.equal(calls.length, 1, "handler ran for valid arguments");
  assert.match(ok.content[0].text, /"live":true/, "target payload returned verbatim");
  assert.match(ok.content[0].text, /srv-123/);

  const bad = (await catalog.invoke("render_service_health", { serviceId: 42 }, {})) as any;
  assert.equal(bad.isError, true, "invalid arguments rejected");
  assert.match(bad.content[0].text, /serviceId/, "field-level error names the field");
  assert.equal(calls.length, 1, "handler NEVER runs on invalid arguments (no phantom success)");

  const unknown = (await catalog.invoke("render_service_healht", {}, {})) as any;
  assert.equal(unknown.isError, true);
  assert.match(unknown.content[0].text, /render_service_health/, "closest real tool suggested");
  assert.equal(calls.length, 1, "unknown tool invokes nothing");
});

// ─── ৪. destructive needs confirm; meta recursion blocked ────────────────
await RequestContextStore.run(admin, async () => {
  const { catalog, calls } = buildCatalog();
  const refused = (await catalog.invoke("action_redis_flush", { prefix: "x" }, {})) as any;
  assert.equal(refused.isError, true);
  assert.match(refused.content[0].text, /destructive/);
  assert.equal(calls.length, 0, "destructive tool not executed without confirm");

  const allowed = (await catalog.invoke("action_redis_flush", { prefix: "x" }, {}, { confirm: true })) as any;
  assert.equal(calls.length, 1);
  assert.match(allowed.content[0].text, /flushed/);

  const recursion = (await catalog.invoke(TOWER_MASTER_TOOLS[2], {}, {})) as any;
  assert.equal(recursion.isError, true);
  assert.match(recursion.content[0].text, /recursion/);
});

// ─── ৫. RBAC: zero-trust context sees nothing, cannot describe ────────────
await RequestContextStore.run(guest, async () => {
  const { catalog, calls } = buildCatalog();
  const page = catalog.search({});
  assert.equal(page.total, 0, "unauthenticated caller sees an empty registry");
  const described = catalog.describe("render_service_health");
  assert.equal(described.ok, false, "describe is denied without authorization");
  const invoked = (await catalog.invoke("render_service_health", { serviceId: "x" }, {})) as any;
  assert.equal(invoked.isError, true, "invoke is denied without authorization");
  assert.equal(calls.length, 0);
});

// ─── ৬. e2e over the real MCP SDK ─────────────────────────────────────────
{
  const server = new McpServer({ name: "tower-catalog-test", version: "0.0.0" });
  const catalog = new TowerToolCatalog();
  catalog.record(
    {
      name: "supabase_health",
      description: "Live Supabase health probe.",
      shape: {},
      annotations: { readOnlyHint: true },
    },
    () => ({ content: [{ type: "text", text: JSON.stringify({ live: true, db: "up" }) }] }),
  );
  registerTowerCatalogTools(server, catalog);

  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: "tower-catalog-client", version: "0.0.0" });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);

  await RequestContextStore.run(
    { role: "agent", authenticated: true, scopes: defaultClientScopes("agent") },
    async () => {
      const listed = await client.listTools();
      const names = listed.tools.map((tool) => tool.name).sort();
      assert.deepEqual(names, ["tower_catalog", "tower_describe", "tower_invoke"]);

      const catalogResult: any = await client.callTool({ name: "tower_catalog", arguments: { query: "supabase" } });
      const page = JSON.parse(catalogResult.content[0].text);
      assert.equal(page.returned, 1, "e2e catalog finds the registered tool");
      assert.equal(page.tools[0].name, "supabase_health");

      const describeResult: any = await client.callTool({
        name: "tower_describe",
        arguments: { tool: "supabase_health" },
      });
      const described = JSON.parse(describeResult.content[0].text);
      assert.equal(described.name, "supabase_health");
      assert.equal(described.risk, "read");

      const invokeResult: any = await client.callTool({
        name: "tower_invoke",
        arguments: { tool: "supabase_health", arguments: {} },
      });
      assert.match(invokeResult.content[0].text, /"live":true/, "e2e invoke returns real target payload");

      const missingResult: any = await client.callTool({
        name: "tower_invoke",
        arguments: { tool: "nope_tool", arguments: {} },
      });
      assert.equal(missingResult.isError, true, "e2e unknown tool fails closed");
    },
  );

  await client.close();
  await server.close();
}

console.log("test_tower_catalog: OK (6 groups — discovery, describe, invoke, destructive, RBAC, e2e)");
