import { env } from "../../lib/env.js";
import { httpRequest, bearerAuth } from "../../lib/http.js";
import { evaluateCloudflareProbe } from "../../diagnostics/cloudflare-evidence.js";

export async function getWorkerStatus(): Promise<unknown> {
  if (!env.cloudflare.workerUrl) {
    throw new Error("SUPREMEAI_CF_WORKER_URL is not configured.");
  }
  
  const start = Date.now();
  // Call the ping worker directly
  try {
    const res = await httpRequest(env.cloudflare.workerUrl, { method: "GET" });
    const probe = evaluateCloudflareProbe({
      providerReachable: res.ok,
      httpStatus: res.status,
      body: res.data,
      deployedCommit: (res.data as any)?.build?.deployed_commit ?? (res.data as any)?.commit ?? null,
      expectedCommit: (res.data as any)?.build?.expected_commit ?? null,
    });
    return {
      status: probe.status,
      httpStatus: res.status,
      workerResponse: res.data,
      checks: probe.checks,
      latencyMs: Date.now() - start
    };
  } catch (e) {
    const probe = evaluateCloudflareProbe({
      providerReachable: false,
      httpStatus: null,
      body: (e as Error).message,
    });
    return {
      status: probe.status,
      message: (e as Error).message,
      checks: probe.checks,
      latencyMs: Date.now() - start
    };
  }
}

export async function getAnalytics(): Promise<unknown> {
  const { accountId, apiToken } = env.cloudflare;
  if (!accountId || !apiToken) {
    throw new Error("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN in env.");
  }

  // Cloudflare GraphQL API for generic worker analytics or zone analytics is complex.
  // We'll verify auth by fetching the account details or workers list instead as a proxy for analytics access right now.
  const res = await httpRequest(`https://api.cloudflare.com/client/v4/accounts/${accountId}/workers/scripts`, {
    headers: bearerAuth(apiToken)
  });
  
  const data = res.data as any;
  if (data.success) {
    return {
      message: "Successfully authenticated with Cloudflare API.",
      workersDeployed: data.result ? data.result.map((w: any) => w.id) : [],
    };
  } else {
    throw new Error(`Cloudflare API Error: ${JSON.stringify(data.errors)}`);
  }
}
