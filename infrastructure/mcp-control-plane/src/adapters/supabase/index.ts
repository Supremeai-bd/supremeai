import { buildAccountRegistry } from "../../registry/account.registry.js";
import { httpRequest, bearerAuth } from "../../lib/http.js";

function getSupabaseConfig(accountId: string) {
  const accounts = buildAccountRegistry();
  const account = accounts.find((a) => a.id === accountId && a.provider === "supabase");
  if (!account) throw new Error(`Supabase account not found: ${accountId}`);
  if (!account.available) throw new Error(`Supabase account is not configured/available: ${accountId}`);

  const apiKey = process.env[account.apiKeyRef];
  const url = account.url;
  if (!apiKey || !url) throw new Error(`Missing Supabase URL or Key in env for: ${accountId}`);
  return { url, apiKey };
}

function supabaseHeaders(apiKey: string) {
  return {
    apikey: apiKey,
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  };
}

export async function getHealth(accountId: string): Promise<unknown> {
  const { url, apiKey } = getSupabaseConfig(accountId);
  // Ping the PostgREST root endpoint
  const res = await httpRequest(`${url}/rest/v1/`, {
    headers: supabaseHeaders(apiKey),
  });
  return {
    status: res.ok ? "healthy" : "degraded",
    latencyMs: res.latencyMs,
    version: (res.data as any).version || "unknown",
  };
}

export async function getAuthUsers(accountId: string): Promise<unknown> {
  const { url, apiKey } = getSupabaseConfig(accountId);
  // Use the Auth Admin API to fetch users (requires service_role key)
  // Endpoint: GET /auth/v1/admin/users
  try {
    const res = await httpRequest(`${url}/auth/v1/admin/users`, {
      headers: supabaseHeaders(apiKey),
    });
    const users = (res.data as any).users || [];
    return {
      totalUsers: users.length,
      message: "Returned total users (paginated limit applies)",
    };
  } catch (err) {
    throw new Error(`Failed to fetch auth users: ${(err as Error).message}`);
  }
}
