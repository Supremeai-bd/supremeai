import { env } from "../../lib/env.js";
import { httpRequest, bearerAuth } from "../../lib/http.js";

export async function checkStripe(): Promise<unknown> {
  const { secretKey } = env.stripe;
  if (!secretKey) throw new Error("STRIPE_SECRET_KEY is not configured.");

  const start = Date.now();
  // Fetch account details to verify the key
  const res = await httpRequest(`https://api.stripe.com/v1/account`, {
    headers: bearerAuth(secretKey)
  });

  return {
    status: "healthy",
    accountId: (res.data as any).id,
    latencyMs: Date.now() - start
  };
}

export async function checkQdrant(): Promise<unknown> {
  const { url, apiKey } = env.qdrant;
  if (!url) throw new Error("QDRANT_URL is not configured.");

  const start = Date.now();
  const headers = apiKey ? { "api-key": apiKey } : undefined;
  
  // Qdrant health endpoint
  const res = await httpRequest(`${url}/healthz`, { headers });

  return {
    status: "healthy",
    message: res.data,
    latencyMs: Date.now() - start
  };
}

export async function checkVercel(): Promise<unknown> {
  const { token, projectId } = env.vercel;
  if (!token) throw new Error("VERCEL_TOKEN is not configured.");

  const start = Date.now();
  // Fetch deployments for the project or just verify auth
  let url = "https://api.vercel.com/v6/deployments?limit=1";
  if (projectId) url += `&projectId=${projectId}`;

  const res = await httpRequest(url, { headers: bearerAuth(token) });
  const data = res.data as any;

  return {
    status: "healthy",
    latestDeployments: data.deployments ? data.deployments.length : 0,
    latencyMs: Date.now() - start
  };
}

export async function checkFirecrawl(): Promise<unknown> {
  const { apiKeys } = env.firecrawl;
  if (apiKeys.length === 0) throw new Error("FIRECRAWL_API_KEY is not configured.");

  const start = Date.now();
  // We can just ping their API or scrape a simple dummy URL to verify.
  // Assuming a health endpoint or just checking the scrape endpoint with a malformed request to see if it's 401.
  // A generic request to /v0/scrape to test Auth.
  try {
    await httpRequest("https://api.firecrawl.dev/v0/scrape", {
      method: "POST",
      headers: bearerAuth(apiKeys[0]),
      body: { url: "https://example.com" }
    });
  } catch (e: any) {
    if (e.message && e.message.includes("401")) {
      throw new Error("Firecrawl API Error: Unauthorized");
    }
  }

  return {
    status: "healthy",
    latencyMs: Date.now() - start
  };
}

export async function checkKaggle(): Promise<unknown> {
  const { tokens } = env.kaggle;
  if (tokens.length === 0) throw new Error("KAGGLE_API_TOKENS is not configured.");

  // For Kaggle, tokens usually come as 'username:key' Base64 for Basic Auth.
  const token = tokens[0];
  const auth = Buffer.from(token).toString('base64');
  
  const start = Date.now();
  const res = await httpRequest("https://www.kaggle.com/api/v1/competitions/list", {
    headers: { Authorization: `Basic ${auth}` }
  });

  return {
    status: "healthy",
    latencyMs: Date.now() - start
  };
}
