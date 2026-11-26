import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore, roleRank } from "../policy/auth.context.js";
import { globalApprovalManager, type ApprovalRequest } from "../policy/approvals/lifecycle.js";
import { globalHITLManager } from "../policy/approvals/hitl.js";
import { globalRiskEngine } from "../policy/risk.engine.js";

// বাংলা মন্তব্য: agent, admin ও supremeadmin রোলের জন্য অনুমতি যাচাই।
function requireAgentOrAbove(): void {
  if (roleRank(RequestContextStore.getRole()) < 1) {
    throw new Error("Forbidden: agent, admin, or supremeadmin role required");
  }
}

// বাংলা মন্তব্য: #757-এর ফাঁক বন্ধ — রেপো allowlist ও ব্রাঞ্চ গার্ড থাকলেও মানব-অনুমোদন
// ছিল না। রোল-ভিত্তিক গার্ড (requireAgentOrAbove) "কে" ঠিক করে, কিন্তু "মানুষ সম্মত কি না"
// ঠিক করে না। তাই admin-এর নিচের প্রতিটি রোলকে HITL অনুমোদনের মধ্য দিয়ে যেতে হবে —
// ঠিক guardian.tools.ts-এর merge_pr প্যাটার্ন অনুসরণ করে।
const HITL_EXEMPT_RANK = 2; // admin (2) ও supremeadmin (3) নিজেরাই অনুমোদনকারী

export interface HitlDecision {
  request: ApprovalRequest;
  riskLevel: ReturnType<typeof globalRiskEngine.evaluate>;
}

/**
 * বাংলা মন্তব্য: admin-এর নিচের রোলে একটি approval request তৈরি করে HITL-এ পাঠায়।
 * রিটার্ন করা request-টি APPROVED হলে তবেই কলার আসল কাজটি করতে পারবে।
 * admin+ হলে null ফেরত দেয় (তারা নিজেরাই অনুমোদনকারী, তাই দ্বিগুণ বাধা নয়)।
 */
export async function requestWriteApproval(
  action: "push_file" | "merge_pr",
  metadata: Record<string, unknown>,
): Promise<HitlDecision | null> {
  if (roleRank(RequestContextStore.getRole()) >= HITL_EXEMPT_RANK) return null;

  const request = globalApprovalManager.createRequest({ provider: "github", action }, metadata);
  const riskLevel = globalRiskEngine.evaluate({ provider: "github", action });
  await globalHITLManager.requestApproval(request, riskLevel);
  return { request, riskLevel };
}

/**
 * বাংলা মন্তব্য: কলার ইতিমধ্যে একটি অনুমোদিত request উপস্থাপন করেছে কি না যাচাই।
 * fail-closed — requestId না থাকলে বা APPROVED না হলে ব্যর্থ।
 */
export function assertApproved(requestId: string | undefined, action: string): void {
  if (!requestId) {
    throw new Error(
      `Forbidden: '${action}' requires human approval (HITL). ` +
        `Call once without approvalRequestId to receive a request ID, approve it via 'policy.approve' (admin role), ` +
        `then retry with approvalRequestId set.`,
    );
  }
  const resolved = globalApprovalManager.getRequest(requestId);
  if (!resolved) {
    throw new Error(`Forbidden: approval request '${requestId}' not found or expired.`);
  }
  if (resolved.state !== "APPROVED") {
    throw new Error(
      `Forbidden: approval request '${requestId}' is ${resolved.state}, not APPROVED. ` +
        `An admin must approve it via 'policy.approve' first.`,
    );
  }
}

// বাংলা মন্তব্য: সব নতুন 3rd-party ইন্টিগ্রেশন এবং মিসিং কোর অ্যাকশন টুলস এক জায়গায়।
async function httpJson(url: string, init: RequestInit = {}): Promise<unknown> {
  const res = await fetch(url, init);
  const text = await res.text();
  let data: unknown = text;
  try {
    data = JSON.parse(text);
  } catch {
    // keep raw text
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${typeof data === "string" ? data : JSON.stringify(data)}`);
  }
  return data;
}

function ok(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

function err(e: unknown) {
  return { isError: true, content: [{ type: "text" as const, text: `Error: ${(e as Error).message}` }] };
}

function infisicalCtx(environment?: string, secretPath?: string) {
  const token = process.env.INFISICAL_TOKEN;
  const projectId = process.env.INFISICAL_PROJECT_ID;
  if (!token || !projectId) throw new Error("INFISICAL_TOKEN or INFISICAL_PROJECT_ID not configured");
  const env = environment || process.env.INFISICAL_ENV || "prod";
  const path = secretPath || "/";
  const qs = new URLSearchParams({ workspaceId: projectId, environment: env, secretPath: path });
  return { token, projectId, env, path, qs };
}

// বাংলা মন্তব্য: সুপ্রিম এআই অনুমোদিত রিপোজিটরি তালিকা (Allowlist - Default-Deny)
export const ALLOWED_ORGS = new Set(["supremeai-bd"]);
export const ALLOWED_REPOS = new Set(["supremeai", "supremeai-public"]);

export function assertAuthorizedRepo(owner: string, repo: string, tool: string): void {
  if (!ALLOWED_ORGS.has(owner.trim().toLowerCase()) || !ALLOWED_REPOS.has(repo.trim().toLowerCase())) {
    throw new Error(`Forbidden: Tool '${tool}' is restricted to Supremeai-bd organization repositories only (${owner}/${repo} is not permitted).`);
  }
}

// বাংলা মন্তব্য: সুরক্ষিত প্রোডাকশন ব্রাঞ্চে সরাসরি পুশ প্রতিরোধ (No direct push to main/master)
export function assertSafeBranch(branch: string | undefined, tool: string): void {
  const b = (branch || "main").trim().toLowerCase();
  if (b === "main" || b === "master" || b.startsWith("refs/heads/main") || b.startsWith("refs/heads/master")) {
    throw new Error(`Forbidden: Direct push to protected branch '${branch || "main"}' is prohibited by SupremeAI Constitution. Agents must push to a dedicated 'agent/*' or 'feature/*' branch and open a PR.`);
  }
}

// বাংলা মন্তব্য: সংবেদনশীল ফাইল সুরক্ষা (.env*, credentials, keys, pem সম্পূর্ণ ব্লক)
export const SENSITIVE_PATH_PATTERNS = [
  /(?:^|\/)\.env(?:\.|$)/i,
  /(?:^|\/)\.git\//i,
  /credential/i,
  /id_rsa/i,
  /\.(?:pem|key|p12|pfx)$/i,
  /token_vault/i,
  /secrets?\./i,
];

export function assertSafeFilePath(path: string, tool: string): void {
  const normalized = path.replace(/\\/g, "/");
  if (SENSITIVE_PATH_PATTERNS.some((p) => p.test(normalized))) {
    throw new Error(`Forbidden: Direct write to sensitive path '${path}' is blocked by '${tool}' security policy.`);
  }
}

export async function registerIntegrationTools(server: McpServer): Promise<void> {
  // ── GitHub: Push File & Merge PR ──
  server.tool(
    "github.push_file",
    "Create or update a file in an authorized GitHub repository via Contents API (main branch direct-push blocked).",
    {
      owner: z.string(),
      repo: z.string(),
      path: z.string(),
      message: z.string(),
      content: z.string().describe("UTF-8 file content"),
      branch: z.string().optional(),
      sha: z.string().optional().describe("Required when updating an existing file"),
    },
    { readOnlyHint: false, destructiveHint: true },
    async ({ owner, repo, path, message, content, branch, sha }) => {
      try {
        requireAgentOrAbove();
        assertAuthorizedRepo(owner, repo, "github.push_file");
        assertSafeBranch(branch, "github.push_file");
        assertSafeFilePath(path, "github.push_file");

        const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
        if (!token) throw new Error("GITHUB_TOKEN / GH_TOKEN not configured");
        const body: Record<string, unknown> = {
          message,
          content: Buffer.from(content, "utf8").toString("base64"),
        };
        if (branch) body.branch = branch;
        if (sha) body.sha = sha;
        const data = await httpJson(`https://api.github.com/repos/${owner}/${repo}/contents/${path}`, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  server.tool(
    "github.merge_pr",
    "Merge an open pull request in an authorized GitHub repository.",
    {
      owner: z.string(),
      repo: z.string(),
      pull_number: z.number(),
      merge_method: z.enum(["merge", "squash", "rebase"]).optional(),
      commit_title: z.string().optional(),
      approvalRequestId: z
        .string()
        .optional()
        .describe("HITL request ID from a prior call, already APPROVED by an admin"),
    },
    { readOnlyHint: false, destructiveHint: true },
    async ({ owner, repo, pull_number, merge_method, commit_title, approvalRequestId }) => {
      try {
        requireAgentOrAbove();
        assertAuthorizedRepo(owner, repo, "github.merge_pr");

        // বাংলা মন্তব্য: PR merge সবচেয়ে বিপজ্জনক লেখা — admin-এর নিচে সবসময় HITL
        const pending = await requestWriteApproval("merge_pr", {
          owner, repo, pullNumber: pull_number, mergeMethod: merge_method ?? "squash",
          requestedBy: RequestContextStore.getRole(),
        });
        if (pending) {
          assertApproved(approvalRequestId, "github.merge_pr");
          return ok({
            action: "HITL_APPROVAL_REQUIRED",
            requestId: pending.request.id,
            approvalRisk: pending.riskLevel,
            expiresInMs: pending.request.expiresAtMs - Date.now(),
            owner, repo, pullNumber: pull_number,
            instruction:
              "An admin must approve this request via 'policy.approve'. " +
              "Then retry this exact call with approvalRequestId set. No PR was merged.",
          });
        }

        const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
        if (!token) throw new Error("GITHUB_TOKEN / GH_TOKEN not configured");
        const data = await httpJson(`https://api.github.com/repos/${owner}/${repo}/pulls/${pull_number}/merge`, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            merge_method: merge_method ?? "squash",
            ...(commit_title ? { commit_title } : {}),
          }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // বাংলা মন্তব্য: অনুমোদিত রিপোজিটরিতে (যেমন supremeai-public) নতুন PR খোলার টুল।
  server.tool(
    "github.create_pr",
    "Create a new pull request in an authorized GitHub repository.",
    {
      owner: z.string(),
      repo: z.string(),
      title: z.string().min(1),
      head: z.string().min(1).describe("Source branch containing changes (cannot be main/master)"),
      base: z.string().default("main").describe("Target branch to merge into (default: main)"),
      body: z.string().optional().describe("Pull request description"),
      draft: z.boolean().optional().describe("Create as a draft pull request"),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ owner, repo, title, head, base, body, draft }) => {
      try {
        requireAgentOrAbove();
        assertAuthorizedRepo(owner, repo, "github.create_pr");
        assertSafeBranch(head, "github.create_pr");

        const token = process.env.GITHUB_TOKEN || process.env.GH_TOKEN;
        if (!token) throw new Error("GITHUB_TOKEN / GH_TOKEN not configured");
        const data = await httpJson(`https://api.github.com/repos/${owner}/${repo}/pulls`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title,
            head,
            base,
            ...(body ? { body } : {}),
            ...(draft !== undefined ? { draft } : {}),
          }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Supabase: Delete Rows ──
  server.tool(
    "supabase.delete_rows",
    "Delete rows from a Supabase table matching a PostgREST filter.",
    {
      table: z.string(),
      filter: z.string().describe("PostgREST filter, e.g. 'id=eq.123'"),
    },
    { readOnlyHint: false, destructiveHint: true },
    async ({ table, filter }) => {
      try {
        requireAgentOrAbove();
        const url = process.env.SUPABASE_URL;
        const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY;
        if (!url || !key) throw new Error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured");
        const data = await httpJson(`${url.replace(/\/$/, "")}/rest/v1/${table}?${filter}`, {
          method: "DELETE",
          headers: {
            apikey: key,
            Authorization: `Bearer ${key}`,
            Prefer: "return=representation",
          },
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Infisical: Get, Set & List Secret Keys ──
  server.tool(
    "infisical.get_secret",
    "Read a single secret value from Infisical v3 API.",
    {
      secretName: z.string(),
      environment: z.string().optional(),
      secretPath: z.string().optional(),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ secretName, environment, secretPath }) => {
      try {
        // বাংলা মন্তব্য: শুধুমাত্র admin এবং supremeadmin রোল infisical.get_secret ব্যবহার করতে পারবে।
        const role = RequestContextStore.getRole();
        if (role !== "admin" && role !== "supremeadmin") {
          throw new Error("Forbidden: infisical.get_secret requires admin or supremeadmin role");
        }
        const token = process.env.INFISICAL_TOKEN;
        const projectId = process.env.INFISICAL_PROJECT_ID;
        if (!token || !projectId) throw new Error("INFISICAL_TOKEN or INFISICAL_PROJECT_ID not configured");
        const env = environment || process.env.INFISICAL_ENV || "prod";
        const path = secretPath || "/";
        const qs = new URLSearchParams({ workspaceId: projectId, environment: env, secretPath: path });
        const data = await httpJson(`https://app.infisical.com/api/v3/secrets/raw/${encodeURIComponent(secretName)}?${qs}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  server.tool(
    "infisical.set_secret",
    "Create or update a secret in Infisical v3 API.",
    {
      secretName: z.string(),
      secretValue: z.string(),
      environment: z.string().optional(),
      secretPath: z.string().optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ secretName, secretValue, environment, secretPath }) => {
      try {
        requireAgentOrAbove();
        const { token, projectId, env, path } = infisicalCtx(environment, secretPath);
        const data = await httpJson(`https://app.infisical.com/api/v3/secrets/raw/${encodeURIComponent(secretName)}`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            workspaceId: projectId,
            environment: env,
            secretPath: path,
            secretValue,
            type: "shared",
          }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  server.tool(
    "infisical.list_secret_keys",
    "List Infisical secret key names only (no values) for agent, admin, and supremeadmin.",
    {
      environment: z.string().optional(),
      secretPath: z.string().optional(),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ environment, secretPath }) => {
      try {
        requireAgentOrAbove();
        const { token, env, path, qs } = infisicalCtx(environment, secretPath);
        const data = (await httpJson(`https://app.infisical.com/api/v3/secrets/raw?${qs}`, {
          headers: { Authorization: `Bearer ${token}` },
        })) as { secrets?: Array<{ secretKey?: string }> };
        // বাংলা মন্তব্য: সিক্রেট ভ্যালু বাদ দিয়ে শুধুমাত্র key-এর নাম রিটার্ন করা হচ্ছে।
        const keys = (data?.secrets ?? []).map((s) => s.secretKey).filter(Boolean);
        return ok({ environment: env, secretPath: path, count: keys.length, keys });
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Neon Postgres ──
  server.tool(
    "neon.list_projects",
    "List Neon Postgres projects.",
    {},
    { readOnlyHint: true, idempotentHint: true },
    async () => {
      try {
        requireAgentOrAbove();
        const key = process.env.NEON_API_KEY;
        if (!key) throw new Error("NEON_API_KEY not configured");
        const data = await httpJson("https://console.neon.tech/api/v2/projects", {
          headers: { Authorization: `Bearer ${key}` },
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Resend Email ──
  server.tool(
    "resend.send_email",
    "Send a transactional email via Resend API.",
    {
      to: z.union([z.string(), z.array(z.string())]),
      subject: z.string(),
      html: z.string(),
      from: z.string().optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ to, subject, html, from }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.RESEND_API_KEY;
        if (!key) throw new Error("RESEND_API_KEY not configured");
        const sender = from || process.env.RESEND_FROM || "onboarding@resend.dev";
        const data = await httpJson("https://api.resend.com/emails", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${key}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ from: sender, to, subject, html }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Discord Webhook ──
  server.tool(
    "discord.send_webhook",
    "Send a message to a configured Discord webhook.",
    {
      content: z.string(),
      username: z.string().optional(),
      webhookUrl: z.string().optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ content, username, webhookUrl }) => {
      try {
        requireAgentOrAbove();
        const url = webhookUrl || process.env.DISCORD_ALERT_WEBHOOK || process.env.DISCORD_WEBHOOK_URL;
        if (!url) throw new Error("DISCORD_WEBHOOK_URL not configured");
        const data = await httpJson(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content, ...(username ? { username } : {}) }),
        });
        return ok(data ?? { sent: true });
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Sentry Issues ──
  server.tool(
    "sentry.list_issues",
    "List recent unresolved Sentry issues for an organization/project.",
    {
      organizationSlug: z.string(),
      projectSlug: z.string(),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ organizationSlug, projectSlug }) => {
      try {
        requireAgentOrAbove();
        const token = process.env.SENTRY_AUTH_TOKEN;
        if (!token) throw new Error("SENTRY_AUTH_TOKEN not configured");
        const data = await httpJson(
          `https://sentry.io/api/0/projects/${organizationSlug}/${projectSlug}/issues/?query=is:unresolved`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── UptimeRobot Monitors ──
  server.tool(
    "uptimerobot.get_monitors",
    "Fetch UptimeRobot monitors and their status.",
    {},
    { readOnlyHint: true, idempotentHint: true },
    async () => {
      try {
        requireAgentOrAbove();
        const key = process.env.UPTIMEROBOT_API_KEY;
        if (!key) throw new Error("UPTIMEROBOT_API_KEY not configured");
        const data = await httpJson("https://api.uptimerobot.com/v2/getMonitors", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: key, format: "json" }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── E2B Sandbox ──
  server.tool(
    "e2b.create_sandbox",
    "Create an E2B cloud code sandbox.",
    {
      templateID: z.string().optional(),
      timeout: z.number().optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ templateID, timeout }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.E2B_API_KEY;
        if (!key) throw new Error("E2B_API_KEY not configured");
        const data = await httpJson("https://api.e2b.dev/sandboxes", {
          method: "POST",
          headers: {
            "X-API-Key": key,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            templateID: templateID ?? "base",
            ...(timeout ? { timeout } : {}),
          }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Cookies Pool Health Check ──
  server.tool(
    "cookies.check_pool",
    "Check whether configured cookie pool env vars are present and non-empty without exposing values.",
    {},
    { readOnlyHint: true, idempotentHint: true },
    async () => {
      try {
        requireAgentOrAbove();
        const cookieKeys = [
          "AI_FLEET_COOKIES_ENC",
          "AI_FLEET_COOKIES_GZIP_B64",
          "SUPREMEAI_GEMINI_COOKIES",
          "SUPREMEAI_GEMINI_1PSID",
          "SUPREMEAI_GEMINI_3PSID",
        ];
        // বাংলা মন্তব্য: কুকি ভ্যালু প্রকাশ না করে শুধুমাত্র কনফিগারড ও ভ্যালিড কিনা তা চেক করা হচ্ছে।
        const results = cookieKeys.map((key) => {
          const val = (process.env[key] || "").trim();
          return {
            key,
            configured: val.length > 0,
            length: val.length,
          };
        });
        return ok({
          total: results.length,
          configuredCount: results.filter((r) => r.configured).length,
          cookies: results,
        });
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── E2B: Run Code in Sandbox ──
  server.tool(
    "e2b.run_code",
    "Execute code inside an existing E2B sandbox.",
    {
      sandboxId: z.string(),
      code: z.string(),
      language: z.enum(["python", "javascript", "bash"]).optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ sandboxId, code, language }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.E2B_API_KEY;
        if (!key) throw new Error("E2B_API_KEY not configured");
        const data = await httpJson(`https://api.e2b.dev/sandboxes/${encodeURIComponent(sandboxId)}/commands`, {
          method: "POST",
          headers: { "X-API-Key": key, "Content-Type": "application/json" },
          body: JSON.stringify({ cmd: language === "bash" ? code : `${language ?? "python"} -c ${JSON.stringify(code)}` }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Neon: Create & Delete Branch ──
  server.tool(
    "neon.create_branch",
    "Create a Neon Postgres branch for isolated testing.",
    {
      projectId: z.string().optional(),
      name: z.string().optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ projectId, name }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.NEON_API_KEY;
        const pid = projectId || process.env.NEON_PROJECT_ID;
        if (!key || !pid) throw new Error("NEON_API_KEY or NEON_PROJECT_ID not configured");
        const data = await httpJson(`https://console.neon.tech/api/v2/projects/${pid}/branches`, {
          method: "POST",
          headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
          body: JSON.stringify({ branch: name ? { name } : {} }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  server.tool(
    "neon.delete_branch",
    "Delete a Neon Postgres branch.",
    {
      projectId: z.string().optional(),
      branchId: z.string(),
    },
    { readOnlyHint: false, destructiveHint: true },
    async ({ projectId, branchId }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.NEON_API_KEY;
        const pid = projectId || process.env.NEON_PROJECT_ID;
        if (!key || !pid) throw new Error("NEON_API_KEY or NEON_PROJECT_ID not configured");
        const data = await httpJson(`https://console.neon.tech/api/v2/projects/${pid}/branches/${branchId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${key}` },
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Upstash Redis: Set & Delete Key ──
  server.tool(
    "redis.set_key",
    "Set a key-value pair in Upstash Redis via REST API.",
    {
      key: z.string(),
      value: z.string(),
      exSeconds: z.number().optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ key, value, exSeconds }) => {
      try {
        requireAgentOrAbove();
        const url = process.env.UPSTASH_REDIS_REST_URL;
        const token = process.env.UPSTASH_REDIS_REST_TOKEN;
        if (!url || !token) throw new Error("UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN not configured");
        const cmd = exSeconds ? ["SET", key, value, "EX", String(exSeconds)] : ["SET", key, value];
        const data = await httpJson(url, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify(cmd),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  server.tool(
    "redis.delete_key",
    "Delete a key from Upstash Redis via REST API.",
    { key: z.string() },
    { readOnlyHint: false, destructiveHint: true },
    async ({ key }) => {
      try {
        requireAgentOrAbove();
        const url = process.env.UPSTASH_REDIS_REST_URL;
        const token = process.env.UPSTASH_REDIS_REST_TOKEN;
        if (!url || !token) throw new Error("UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN not configured");
        const data = await httpJson(url, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify(["DEL", key]),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── LaunchDarkly: Get & Toggle Flags ──
  server.tool(
    "launchdarkly.get_flags",
    "List LaunchDarkly feature flags for a project.",
    { projectKey: z.string().optional() },
    { readOnlyHint: true, idempotentHint: true },
    async ({ projectKey }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.LAUNCHDARKLY_API_KEY;
        if (!key) throw new Error("LAUNCHDARKLY_API_KEY not configured");
        const data = await httpJson(`https://app.launchdarkly.com/api/v2/flags/${projectKey ?? "default"}`, {
          headers: { Authorization: key },
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  server.tool(
    "launchdarkly.toggle_flag",
    "Turn a LaunchDarkly feature flag on or off in an environment.",
    {
      projectKey: z.string().optional(),
      flagKey: z.string(),
      environmentKey: z.string(),
      enabled: z.boolean(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ projectKey, flagKey, environmentKey, enabled }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.LAUNCHDARKLY_API_KEY;
        if (!key) throw new Error("LAUNCHDARKLY_API_KEY not configured");
        const data = await httpJson(
          `https://app.launchdarkly.com/api/v2/flags/${projectKey ?? "default"}/${flagKey}`,
          {
            method: "PATCH",
            headers: { Authorization: key, "Content-Type": "application/json" },
            body: JSON.stringify({
              patch: [{ op: "replace", path: `/environments/${environmentKey}/on`, value: enabled }],
            }),
          }
        );
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Trigger.dev: Run Task ──
  server.tool(
    "trigger.run_task",
    "Trigger a background task in Trigger.dev.",
    {
      taskIdentifier: z.string(),
      payload: z.record(z.string(), z.unknown()).optional(),
    },
    { readOnlyHint: false, destructiveHint: false },
    async ({ taskIdentifier, payload }) => {
      try {
        requireAgentOrAbove();
        const key = process.env.TRIGGER_SECRET_KEY;
        if (!key) throw new Error("TRIGGER_SECRET_KEY not configured");
        const data = await httpJson(`https://api.trigger.dev/api/v1/tasks/${encodeURIComponent(taskIdentifier)}/trigger`, {
          method: "POST",
          headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
          body: JSON.stringify({ payload: payload ?? {} }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );

  // ── Supabase Storage: List Files ──
  server.tool(
    "supabase.storage_list",
    "List files in a Supabase Storage bucket.",
    {
      bucket: z.string(),
      prefix: z.string().optional(),
    },
    { readOnlyHint: true, idempotentHint: true },
    async ({ bucket, prefix }) => {
      try {
        requireAgentOrAbove();
        const url = process.env.SUPABASE_URL;
        const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY;
        if (!url || !key) throw new Error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured");
        const data = await httpJson(`${url.replace(/\/$/, "")}/storage/v1/object/list/${encodeURIComponent(bucket)}`, {
          method: "POST",
          headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
          body: JSON.stringify({ prefix: prefix ?? "", limit: 100 }),
        });
        return ok(data);
      } catch (e) {
        return err(e);
      }
    }
  );
}
