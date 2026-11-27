/**
 * Tower master tools — progressive disclosure WITHOUT merging schemas.
 *
 * WHY THIS SHAPE (and why it is not the mega-tool that TOOL-EXPOSURE.md §8
 * rejected):
 *
 *   The tower exposes ~178 tools. Handing all of them to an agent in
 *   `tools/list` costs context on every turn and measurably degrades tool
 *   selection, which is exactly the failure mode the discovery filter exists
 *   to soften. But a single `supremeai(operation, …)` mega-tool was rightly
 *   rejected: it collapses per-tool zod validation and blurs the
 *   tool→provider→action→R-level policy SSoT (#2429).
 *
 *   These three tools keep BOTH properties:
 *
 *     tower_catalog  → searchable index of what the caller may actually call
 *     tower_describe → the exact contract of ONE tool (params, risk, hints)
 *     tower_invoke   → dispatch to that tool's ORIGINAL handler, with the
 *                      ORIGINAL zod schema parsed first and the ORIGINAL
 *                      governed wrapper (RBAC, per-tool rate limit, payload
 *                      cap, timeout, truncation) still in the path.
 *
 *   Nothing is merged, nothing is re-implemented, no second metadata source
 *   is introduced: the catalog is populated from the same registration call
 *   that already routes through the governance wrapper.
 *
 * ANTI-HALLUCINATION CONTRACT (why agents get real data, not plausible text):
 *   1. `tower_invoke` never fabricates a payload. It returns the target
 *      tool's own response verbatim, or `isError` with the target's own error.
 *   2. Arguments are validated against the target tool's REAL zod shape before
 *      dispatch; invalid input yields a structured field-level error, so a
 *      model can self-correct instead of silently "succeeding".
 *   3. `tower_describe` is the only sanctioned way to learn a contract — it
 *      reflects the registered schema, so it cannot drift from the call path.
 *   4. Unknown tool names return the closest real names, never an invented one.
 *   5. Destructive tools require an explicit `confirm: true` at the master
 *      layer as well as inside the target tool.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { toolAccessError } from "../policy/mcp-access.js";
import { toolListAccessError } from "../policy/tool-visibility.js";

export type ToolRisk = "read" | "write" | "destructive";

/** Wire names of the master tools themselves (sanitized form). */
export const TOWER_MASTER_TOOLS = ["tower_catalog", "tower_describe", "tower_invoke"] as const;

export interface CatalogRegistration {
  /** Sanitized wire name (dots already replaced by the index.ts wrapper). */
  name: string;
  description: string;
  /** The tool's live zod raw shape, when the registration surface supplies one. */
  shape?: unknown;
  annotations?: Record<string, unknown>;
}

type ToolHandler = (args: unknown, extra: unknown) => unknown;

interface CatalogEntry extends CatalogRegistration {
  domain: string;
  risk: ToolRisk;
  handler: ToolHandler;
}

export interface CatalogPage {
  tools: Array<{
    name: string;
    domain: string;
    risk: ToolRisk;
    summary: string;
  }>;
  total: number;
  returned: number;
  nextCursor?: string;
  note: string;
}

function domainOf(name: string): string {
  const [head] = name.split("_");
  return (head || name).toLowerCase();
}

function riskOf(annotations: Record<string, unknown> | undefined): ToolRisk {
  if (!annotations) return "read";
  if (annotations.destructiveHint === true) return "destructive";
  if (annotations.readOnlyHint === false) return "write";
  return "read";
}

function summarize(description: string, max = 140): string {
  const firstSentence = description.split(/(?<=\.)\s/)[0] ?? description;
  const text = firstSentence.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Best-effort, defensive reflection over a zod schema — never throws. */
function describeSchema(shape: unknown): Record<string, { type: string; required: boolean; description?: string }> {
  const out: Record<string, { type: string; required: boolean; description?: string }> = {};
  if (!shape || typeof shape !== "object") return out;
  for (const [key, value] of Object.entries(shape as Record<string, unknown>)) {
    const field = value as {
      description?: unknown;
      isOptional?: () => boolean;
      _def?: { typeName?: string; type?: string };
    };
    let required = true;
    try {
      if (typeof field?.isOptional === "function" && field.isOptional()) required = false;
    } catch {
      required = true;
    }
    const typeName = field?._def?.typeName ?? field?._def?.type ?? "unknown";
    out[key] = {
      type: String(typeName).replace(/^Zod/, "").toLowerCase(),
      required,
      ...(typeof field?.description === "string" ? { description: field.description } : {}),
    };
  }
  return out;
}

function levenshtein(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dp: number[][] = Array.from({ length: rows }, () => new Array<number>(cols).fill(0));
  for (let i = 0; i < rows; i++) dp[i][0] = i;
  for (let j = 0; j < cols; j++) dp[0][j] = j;
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
  }
  return dp[rows - 1][cols - 1];
}

/**
 * The registry is populated by the SAME interception point in `index.ts` that
 * already wraps every handler in the governance gate. One write path, one read
 * path — no parallel metadata layer to drift (#2429).
 */
export class TowerToolCatalog {
  private readonly entries = new Map<string, CatalogEntry>();

  record(registration: CatalogRegistration, handler: ToolHandler): void {
    const name = registration.name;
    if (TOWER_MASTER_TOOLS.includes(name as (typeof TOWER_MASTER_TOOLS)[number])) return;
    this.entries.set(name, {
      ...registration,
      name,
      domain: domainOf(name),
      risk: riskOf(registration.annotations),
      handler,
    });
  }

  get size(): number {
    return this.entries.size;
  }

  /** Tools the CURRENT caller may both see and call (list ⊆ call invariant). */
  private visible(): CatalogEntry[] {
    return [...this.entries.values()].filter((entry) => toolListAccessError(entry.name) === null);
  }

  search(options: { query?: string; domain?: string; risk?: ToolRisk; limit?: number; cursor?: string }): CatalogPage {
    const query = (options.query ?? "").trim().toLowerCase();
    const domain = (options.domain ?? "").trim().toLowerCase();
    const limit = Math.min(Math.max(options.limit ?? 25, 1), 100);
    const all = this.visible()
      .filter((entry) => (domain ? entry.domain === domain : true))
      .filter((entry) => (options.risk ? entry.risk === options.risk : true))
      .filter((entry) => {
        if (!query) return true;
        return (
          entry.name.toLowerCase().includes(query) ||
          entry.description.toLowerCase().includes(query)
        );
      })
      .sort((a, b) => a.name.localeCompare(b.name));

    const offset = options.cursor ? Math.max(Number.parseInt(options.cursor, 10) || 0, 0) : 0;
    const page = all.slice(offset, offset + limit);
    const nextOffset = offset + page.length;

    return {
      tools: page.map((entry) => ({
        name: entry.name,
        domain: entry.domain,
        risk: entry.risk,
        summary: summarize(entry.description),
      })),
      total: all.length,
      returned: page.length,
      ...(nextOffset < all.length ? { nextCursor: String(nextOffset) } : {}),
      note:
        "Call tower_describe({tool}) for the exact parameter contract before tower_invoke. " +
        "Summaries are truncated descriptions; the authoritative contract is the registered schema.",
    };
  }

  describe(name: string): { ok: true; tool: Record<string, unknown> } | { ok: false; error: string } {
    const entry = this.entries.get(name);
    if (!entry) return { ok: false, error: this.unknownToolMessage(name) };
    const denial = toolListAccessError(name);
    if (denial) return { ok: false, error: denial };
    return {
      ok: true,
      tool: {
        name: entry.name,
        domain: entry.domain,
        risk: entry.risk,
        description: entry.description,
        annotations: entry.annotations ?? {},
        parameters: describeSchema(entry.shape),
        call: `tower_invoke({ "tool": "${entry.name}", "arguments": { … } })`,
      },
    };
  }

  async invoke(
    name: string,
    args: Record<string, unknown>,
    extra: unknown,
    options: { confirm?: boolean } = {},
  ): Promise<unknown | ToolErrorResult> {
    if (TOWER_MASTER_TOOLS.includes(name as (typeof TOWER_MASTER_TOOLS)[number])) {
      return errorResult(
        `Refusing to invoke '${name}' through tower_invoke (no meta-tool recursion). ` +
          "Call it directly.",
      );
    }
    const entry = this.entries.get(name);
    if (!entry) {
      return errorResult(this.unknownToolMessage(name));
    }

    // Defense in depth: the recorded handler is already the governed wrapper
    // (RBAC + rate limit + timeout), but the master layer re-checks the RBAC
    // gate so the denial is reported as a clean, actionable message and any
    // future registration surface cannot bypass it. NOTE: RBAC only — the
    // client toolProfile is a curation layer ("visibility curates, RBAC
    // enforces"), so a tool hidden from tools/list stays callable here exactly
    // as it would on a direct call.
    const denial = toolAccessError(entry.name);
    if (denial) return errorResult(denial);

    // Destructive targets need an explicit second signal at the master layer,
    // on top of whatever guard the target tool implements itself.
    if (entry.risk === "destructive" && options.confirm !== true) {
      return errorResult(
        `'${name}' is destructive. Re-call tower_invoke with "confirm": true and the same arguments. ` +
          "If you only wanted to inspect it, use tower_describe.",
      );
    }

    // Validate against the TARGET tool's own zod shape — the same schema the
    // SDK would apply on a direct call, so validation is not bypassed.
    if (entry.shape) {
      try {
        const parsed = z.object(entry.shape as z.ZodRawShape).safeParse(args);
        if (!parsed.success) {
          return errorResult(
            `Invalid arguments for '${name}':\n` +
              parsed.error.issues
                .map((issue) => `  - ${issue.path.join(".") || "(root)"}: ${issue.message}`)
                .join("\n") +
              "\nCall tower_describe({ tool: \"" + name + "\" }) for the full contract.",
          );
        }
        args = parsed.data as Record<string, unknown>;
      } catch (err) {
        console.error(err instanceof Error ? err.name : "error");
        // A shape we cannot reflect (non-zod registration surface) must not
        // block the call: the SDK will still validate on the direct path.
      }
    }

    return entry.handler(args, extra);
  }

  private unknownToolMessage(name: string): string {
    const names = this.visible().map((entry) => entry.name);
    const closest = names
      .map((candidate) => ({ candidate, distance: levenshtein(name, candidate) }))
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 5)
      .filter((entry) => entry.distance <= Math.max(3, name.length / 2))
      .map((entry) => entry.candidate);
    const hint = closest.length
      ? `Closest registered tools: ${closest.join(", ")}.`
      : "Use tower_catalog({ query }) to search the registry.";
    return `Unknown tool '${name}'. ${hint} No such tool will be invoked or invented.`;
  }
}

type ToolErrorResult = { isError: true; content: Array<{ type: "text"; text: string }> };

function errorResult(text: string): ToolErrorResult {
  return { isError: true, content: [{ type: "text", text }] };
}

/** Shared singleton — populated by the index.ts registration wrapper. */
export const towerToolCatalog = new TowerToolCatalog();

export function registerTowerCatalogTools(server: McpServer, catalog: TowerToolCatalog = towerToolCatalog): void {
  server.tool(
    "tower_catalog",
    "Search the tower's ENTIRE tool registry (all ~178 tools, including ones hidden from tools/list). " +
      "Returns only tools the current caller is authorized to call, with name, domain, risk and a one-line summary. " +
      "Use this to discover capability, then tower_describe for the exact contract. Never guess a tool name.",
    {
      query: z.string().optional().describe("Substring match on tool name or description"),
      domain: z.string().optional().describe("Filter by domain prefix, e.g. github, render, supabase, memory"),
      risk: z.enum(["read", "write", "destructive"]).optional().describe("Filter by risk class"),
      limit: z.number().int().min(1).max(100).optional().default(25).describe("Page size"),
      cursor: z.string().optional().describe("nextCursor from a previous tower_catalog page"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async (args) => {
      const page = catalog.search(args as Parameters<TowerToolCatalog["search"]>[0]);
      return { content: [{ type: "text" as const, text: JSON.stringify(page, null, 2) }] };
    },
  );

  server.tool(
    "tower_describe",
    "Return the AUTHORITATIVE contract of one tool: description, risk class, annotations and parameter schema, " +
      "reflected from the live registration (it cannot drift from the call path). Call this before tower_invoke.",
    {
      tool: z.string().describe("Tool name as returned by tower_catalog"),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ tool }) => {
      const described = catalog.describe(tool);
      if (!described.ok) return errorResult(described.error);
      return { content: [{ type: "text" as const, text: JSON.stringify(described.tool, null, 2) }] };
    },
  );

  server.tool(
    "tower_invoke",
    "Execute ANY registered tower tool by name, keeping the target's own validation, RBAC, per-tool rate limit, " +
      "timeout and truncation fully in force. Returns the target tool's real response verbatim — never a synthesized " +
      "answer. Invalid arguments produce a field-level error instead of a fake success. Destructive tools need confirm:true.",
    {
      tool: z.string().describe("Exact tool name (sanitized, dots become underscores)"),
      arguments: z
        .record(z.string(), z.unknown())
        .optional()
        .default({})
        .describe("Arguments object for the target tool — see tower_describe for its shape"),
      confirm: z
        .boolean()
        .optional()
        .default(false)
        .describe("Required true when the target tool is destructive"),
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false },
    async (args, extra) => {
      const { tool, arguments: toolArgs, confirm } = args as {
        tool: string;
        arguments?: Record<string, unknown>;
        confirm?: boolean;
      };
      const result = await catalog.invoke(tool, toolArgs ?? {}, extra, { confirm });
      return result as { content: Array<{ type: "text"; text: string }> };
    },
  );
}
