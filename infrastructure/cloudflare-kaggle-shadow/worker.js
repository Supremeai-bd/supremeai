/**
 * SupremeAI Kaggle 24/7 Shadow Node Rotator & Reverse Proxy
 *
 * - Cron Trigger (every 10h): Pushes a background notebook to the next Kaggle
 *   account in KAGGLE_ACCOUNTS_JSON via Kaggle's REST API.
 * - POST /register: Receives the live trycloudflare.com URL from the newly
 *   started Kaggle notebook and stores it in SHADOW_STATE KV.
 * - POST /rotate: Manually triggers rotation to the next Kaggle account.
 * - GET /status: Returns active node metadata (without secrets).
 * - All other requests: Proxied transparently to the active Kaggle node.
 */

const KAGGLE_PUSH_API = "https://www.kaggle.com/api/v1/kernels/push";

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function isAuthorized(request, env) {
  const secret = env.SHADOW_REGISTER_SECRET;
  if (!secret) return false;
  const auth = request.headers.get("Authorization") || "";
  return auth === `Bearer ${secret}`;
}

function buildNotebookPayload(username, workerUrl, registerSecret) {
  const notebookCode = `
import json, os, shutil, subprocess, time, urllib.request

!pip install -q cloudflared
!rm -rf /tmp/supremeai
!git clone --depth 1 https://github.com/Supremeai-bd/supremeai.git /tmp/supremeai
!cd /tmp/supremeai/infrastructure/mcp-control-plane && npm ci --silent && npm run build

mcp_env = os.environ.copy()
mcp_env["MCP_PORT"] = "3771"
mcp_env["TINY_BRAIN_URL"] = "https://njelitltd-tiny-brain.hf.space"
mcp_env["KAGGLE_SHADOW_URL"] = "${workerUrl}"

mcp_proc = subprocess.Popen(
    ["node", "dist/index.js"],
    cwd="/tmp/supremeai/infrastructure/mcp-control-plane",
    env=mcp_env,
)

cf_bin = shutil.which("cloudflared") or "/usr/local/bin/cloudflared"
tunnel_proc = subprocess.Popen(
    [cf_bin, "tunnel", "--url", "http://localhost:3771"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

public_url = None
for _ in range(40):
    line = tunnel_proc.stdout.readline()
    if "trycloudflare.com" in line:
        for word in line.split():
            if "trycloudflare.com" in word:
                public_url = word.strip()
                break
        if public_url:
            break

if public_url and "${workerUrl}":
    req = urllib.request.Request(
        "${workerUrl}/register",
        data=json.dumps({"url": public_url, "account": "${username}"}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer ${registerSecret}",
            "User-Agent": "SupremeAI-Shadow/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("Registered real MCP Tower:", resp.status, public_url)
    except Exception as e:
        print("Registration failed:", e)

mcp_proc.wait()
`.trim();

  const ipynb = {
    cells: [
      {
        cell_type: "code",
        execution_count: null,
        metadata: {},
        outputs: [],
        source: notebookCode.split("\n").map((line) => line + "\n"),
      },
    ],
    metadata: {
      kernelspec: {
        display_name: "Python 3",
        language: "python",
        name: "python3",
      },
    },
    nbformat: 4,
    nbformat_minor: 5,
  };

  return {
    slug: `${username}/supremeai-shadow-node`,
    newTitle: "SupremeAI Shadow Node",
    text: JSON.stringify(ipynb),
    language: "python",
    kernelType: "notebook",
    isPrivate: true,
    enableGpu: false,
    enableInternet: true,
    datasetDataSources: [],
    competitionDataSources: [],
    kernelDataSources: [],
  };
}

async function rotateKaggleNode(env, workerUrl) {
  if (!env.SHADOW_STATE) {
    return { ok: false, error: "SHADOW_STATE KV namespace is not bound" };
  }
  if (!env.KAGGLE_ACCOUNTS_JSON) {
    return { ok: false, error: "KAGGLE_ACCOUNTS_JSON secret is not configured" };
  }

  const accounts = JSON.parse(env.KAGGLE_ACCOUNTS_JSON);
  if (!Array.isArray(accounts) || accounts.length === 0) {
    return { ok: false, error: "KAGGLE_ACCOUNTS_JSON must be a non-empty array" };
  }

  const rawIdx = await env.SHADOW_STATE.get("account_index");
  const idx = rawIdx ? parseInt(rawIdx, 10) % accounts.length : 0;
  const account = accounts[idx];
  const nextIdx = (idx + 1) % accounts.length;

  await env.SHADOW_STATE.put("account_index", String(nextIdx));

  const payload = buildNotebookPayload(
    account.username,
    workerUrl || env.WORKER_PUBLIC_URL || "",
    env.SHADOW_REGISTER_SECRET || ""
  );

  const token = account.token || account.key || "";
  const authHeader = token.startsWith("KGAT_")
    ? `Bearer ${token}`
    : "Basic " + btoa(`${account.username}:${token}`);
  const resp = await fetch(KAGGLE_PUSH_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: authHeader,
    },
    body: JSON.stringify(payload),
  });

  const bodyText = await resp.text();
  return {
    ok: resp.ok,
    status: resp.status,
    pushed_account: account.username,
    next_account_index: nextIdx,
    kaggle_response: bodyText.slice(0, 500),
  };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(rotateKaggleNode(env, env.WORKER_PUBLIC_URL || ""));
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const workerOrigin = `${url.protocol}//${url.host}`;

    if (url.pathname === "/status" && request.method === "GET") {
      if (!env.SHADOW_STATE) {
        return jsonResponse({ ok: false, error: "SHADOW_STATE KV not bound" }, 500);
      }
      const [activeUrl, activeAccount, updatedAt, accountIndex] = await Promise.all([
        env.SHADOW_STATE.get("active_url"),
        env.SHADOW_STATE.get("active_account"),
        env.SHADOW_STATE.get("updated_at"),
        env.SHADOW_STATE.get("account_index"),
      ]);
      return jsonResponse({
        ok: true,
        active_url: activeUrl || null,
        active_account: activeAccount || null,
        updated_at: updatedAt || null,
        next_account_index: accountIndex ? parseInt(accountIndex, 10) : 0,
      });
    }

    if (url.pathname === "/register" && request.method === "POST") {
      if (!isAuthorized(request, env)) {
        return jsonResponse({ ok: false, error: "Unauthorized" }, 401);
      }
      const body = await request.json();
      if (!body.url || !body.url.startsWith("https://")) {
        return jsonResponse({ ok: false, error: "Invalid https url" }, 400);
      }
      await Promise.all([
        env.SHADOW_STATE.put("active_url", body.url),
        env.SHADOW_STATE.put("active_account", body.account || "unknown"),
        env.SHADOW_STATE.put("updated_at", new Date().toISOString()),
      ]);
      return jsonResponse({ ok: true, registered_url: body.url });
    }

    if (url.pathname === "/rotate" && request.method === "POST") {
      if (!isAuthorized(request, env)) {
        return jsonResponse({ ok: false, error: "Unauthorized" }, 401);
      }
      const result = await rotateKaggleNode(env, workerOrigin);
      return jsonResponse(result, result.ok ? 200 : 502);
    }

    // Proxy all other requests to the active Kaggle Shadow Node
    if (!env.SHADOW_STATE) {
      return jsonResponse({ ok: false, error: "SHADOW_STATE KV not bound" }, 500);
    }
    const activeUrl = await env.SHADOW_STATE.get("active_url");
    if (!activeUrl) {
      return jsonResponse(
        { ok: false, error: "No active Kaggle shadow node registered yet" },
        503
      );
    }

    const targetUrl = new URL(url.pathname + url.search, activeUrl);
    const proxyReq = new Request(targetUrl.toString(), {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
    });

    return fetch(proxyReq);
  },
};
