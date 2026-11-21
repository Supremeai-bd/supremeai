import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore, roleRank } from "../policy/auth.context.js";

// বাংলা মন্তব্য: agent, admin ও supremeadmin রোলের জন্য অনুমতি যাচাই।
function requireAgentOrAbove(): void {
  if (roleRank(RequestContextStore.getRole()) < 1) {
    throw new Error("Forbidden: agent, admin, or supremeadmin role required");
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

export async function registerIntegrationTools(server: McpServer): Promise<void> {
  // ── GitHub: Push File & Merge PR ──
  server.tool(
    "github.push_file",
    "Create or update a file in a GitHub repository via Contents API.",
    {
      owner: z.string(),
      repo: z.string(),
      path: z.string(),
      message: z.string(),
      content: z.string().describe("UTF-8 file content"),
      branch: z.string().optional(),
      sha: z.string().optional().describe("Required when updating an existing file"),
    },
    async ({ owner, repo, path, message, content, branch, sha }) => {
      try {
        requireAgentOrAbove();
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
    "Merge an open GitHub pull request.",
    {
      owner: z.string(),
      repo: z.string(),
      pull_number: z.number(),
      merge_method: z.enum(["merge", "squash", "rebase"]).optional(),
      commit_title: z.string().optional(),
    },
    async ({ owner, repo, pull_number, merge_method, commit_title }) => {
      try {
        requireAgentOrAbove();
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

  // ── Supabase: Delete Rows ──
  server.tool(
    "supabase.delete_rows",
    "Delete rows from a Supabase table matching a PostgREST filter.",
    {
      table: z.string(),
      filter: z.string().describe("PostgREST filter, e.g. 'id=eq.123'"),
    },
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
    async ({ secretName, secretValue, environment, secretPath }) => {
      try {
        requireAgentOrAbove();
        const token = process.env.INFISICAL_TOKEN;
        const projectId = process.env.INFISICAL_PROJECT_ID;
        if (!token || !projectId) throw new Error("INFISICAL_TOKEN or INFISICAL_PROJECT_ID not configured");
        const env = environment || process.env.INFISICAL_ENV || "prod";
        const path = secretPath || "/";
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
    async ({ environment, secretPath }) => {
      try {
        requireAgentOrAbove();
        const token = process.env.INFISICAL_TOKEN;
        const projectId = process.env.INFISICAL_PROJECT_ID;
        if (!token || !projectId) throw new Error("INFISICAL_TOKEN or INFISICAL_PROJECT_ID not configured");
        const env = environment || process.env.INFISICAL_ENV || "prod";
        const path = secretPath || "/";
        const qs = new URLSearchParams({ workspaceId: projectId, environment: env, secretPath: path });
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
