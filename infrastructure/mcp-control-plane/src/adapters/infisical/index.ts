import { env } from "../../lib/env.js";
import { httpRequest, bearerAuth } from "../../lib/http.js";

const INFISICAL_URL = "https://app.infisical.com";

async function getAccessToken(): Promise<string> {
  const { clientId, clientSecret } = env.infisical;
  if (!clientId || !clientSecret) {
    throw new Error("Missing INFISICAL_CLIENT_ID or INFISICAL_CLIENT_SECRET");
  }

  const res = await httpRequest(`${INFISICAL_URL}/api/v1/auth/universal-auth/login`, {
    method: "POST",
    body: {
      clientId,
      clientSecret,
    },
  });

  const data = res.data as any;
  if (data.accessToken) {
    return data.accessToken;
  }
  throw new Error("Failed to get Infisical access token");
}

export async function auditSecrets(): Promise<unknown> {
  const { projectId, environment } = env.infisical;
  if (!projectId) {
    throw new Error("Missing INFISICAL_PROJECT_ID");
  }

  const token = await getAccessToken();
  
  try {
    const res = await httpRequest(`${INFISICAL_URL}/api/v3/secrets?workspaceId=${projectId}&environment=${environment}&secretPath=/`, {
      headers: bearerAuth(token),
      timeoutMs: 15000,
    });

    const data = res.data as any;
    if (data.secrets) {
      return data.secrets.map((s: any) => ({
        id: s._id,
        secretKey: s.secretKey,
        version: s.version,
        createdAt: s.createdAt,
      }));
    }
    return data;
  } catch (e) {
    return {
      status: "error",
      message: `Infisical API Error: ${(e as Error).message}`
    };
  }
}

export async function getSyncStatus(): Promise<unknown> {
  const { projectId } = env.infisical;
  const token = await getAccessToken();

  try {
    const res = await httpRequest(`${INFISICAL_URL}/api/v1/workspace/${projectId}/integrations`, {
      headers: bearerAuth(token),
      timeoutMs: 15000,
    });

    return res.data;
  } catch (e) {
    return {
      status: "error",
      message: `Infisical API Error: ${(e as Error).message}`
    };
  }
}

/**
 * Dynamically loads production secrets from Infisical and populates process.env.
 * Does not overwrite existing environment variables.
 */
export async function pullSecretsIntoProcessEnv(): Promise<{ loaded: number; skipped: boolean }> {
  const { clientId, clientSecret, projectId, environment } = env.infisical;
  if (!clientId || !clientSecret || !projectId) {
    return { loaded: 0, skipped: true };
  }

  try {
    const token = await getAccessToken();
    const envSlug = environment === "production" ? "prod" : environment;
    const res = await httpRequest(
      `${INFISICAL_URL}/api/v3/secrets/raw?workspaceId=${projectId}&environment=${envSlug}&secretPath=/`,
      {
        headers: bearerAuth(token),
        timeoutMs: 20000,
      }
    );

    const data = res.data as { secrets?: Array<{ secretKey: string; secretValue: string }> };
    const secrets = data.secrets || [];
    let count = 0;

    for (const secret of secrets) {
      if (secret.secretKey && !process.env[secret.secretKey]) {
        process.env[secret.secretKey] = secret.secretValue;
        count++;
      }
    }

    return { loaded: count, skipped: false };
  } catch (err: any) {
    console.warn(`[Infisical] Warning: unable to auto-load secrets: ${err?.message || err}`);
    return { loaded: 0, skipped: true };
  }
}

