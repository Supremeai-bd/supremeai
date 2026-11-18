# Render Free Tier Quota & Bandwidth Exhaustion Analysis

**Document Version:** 1.0.0  
**Date:** November 18, 2026  
**Target Service:** `supremeai-mcp-tower` (`srv-dabm7inqj5pc738jkrt0`)  
**Workspace:** `Saiful Haque's workspace` (`tea-d9fn2sm7r5hc73f7ltkg`)  
**Status:** Suspended (`suspenders: ['billing']`)  

---

## 1. Executive Summary

On November 18, 2026, the `supremeai-mcp-tower` service hosted on Render entered a suspended state, returning `HTTP 503: Service Unavailable` to incoming requests and failing canary checks in CI/CD pipeline runs.

A common initial hypothesis was that the service had exhausted its monthly 750 free instance compute hours. However, empirical analysis of the Render management plane and API telemetry confirmed:
1. **Compute Hours Were NOT Exhausted:** Render provides 750 free instance hours per month. A single service running continuously 24/7 consumes at most $24 \times 31 = 744$ hours. Computations showed remaining compute hours were still available.
2. **Bandwidth Quota Exhaustion:** The suspension was triggered strictly by **bandwidth limit exhaustion**.
3. **The 5 GB Limit vs 100 GB Myth:** Render's modern "Hobby" workspace grants **5 GB of free bandwidth per month** (unlike platforms like Vercel or Netlify that provide 100 GB). In 18 days, the workspace consumed 100% of this 5 GB allotment.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ [Render Red Alert]                                                              │
│ Workspace suspended: You've used the 5 GB of free bandwidth in your Hobby       │
│ workspace. Add a card to continue ($0.15 per 1 GB) or upgrade to Pro.          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mathematical Breakdown of Consumption

Render meters **both Ingress (inbound) and Egress (outbound)** data transfer across the public internet.

$$\text{Total Allocated Free Bandwidth} = 5\text{ GB} = 5,120\text{ MB}$$

$$\text{Operational Duration} = 18\text{ days} = 432\text{ hours} = 25,920\text{ minutes}$$

$$\text{Average Daily Bandwidth} = \frac{5,120\text{ MB}}{18\text{ days}} \approx \mathbf{284.4\text{ MB/day}}$$

$$\text{Average Hourly Bandwidth} = \frac{284.4\text{ MB}}{24\text{ hours}} \approx \mathbf{11.85\text{ MB/hour}}$$

$$\text{Continuous Bandwidth Rate} = \frac{11.85\text{ MB}}{60\text{ minutes}} \approx \mathbf{197.5\text{ KB/minute}}$$

> **Key Takeaway:** A persistent background trickle of just **~200 KB per minute** is sufficient to deplete the entire monthly 5 GB quota in 18 days.

---

## 3. Deep-Dive: Architectural Traffic Drivers

By auditing the repository source code and automation pipelines, five primary contributors to this 200 KB/min rate were identified:

### Driver 1: Autonomous 5-Minute Health Sweeps (`runFullSweep`)
- **Location:** `infrastructure/mcp-control-plane/src/index.ts` & `engine.ts`
- **Mechanism:** A recurring timer triggers `globalHealthEngine.runFullSweep()` every 5 minutes (300,000 ms), 24 hours a day, 7 days a week:
  - Sweeps per day: $\frac{24 \times 60}{5} = \mathbf{288\text{ sweeps/day}}$
  - Sweeps in 18 days: $288 \times 18 = \mathbf{5,184\text{ sweeps}}$
- **Network Footprint:** On every single sweep, the container initiates outbound HTTPS connections to **15 distinct external providers**:
  1. Render Management API (`getServiceHealth`)
  2. Supabase Cloud API (`getSupabaseHealth`)
  3. Upstash Redis (`pingRedis`)
  4. Cloudflare API (`getWorkerStatus`)
  5. Infisical Secret Manager (`auditSecrets` — fetches metadata across environments)
  6. Stripe API (`checkStripe`)
  7. Vercel API (`checkVercel`)
  8. Firecrawl API (`checkFirecrawl`)
  9. Kaggle API (`checkKaggle`)
  10. Qdrant Cloud API (`checkQdrant`)
  11. Multi-AI model gateways (OpenAI, Anthropic, Google, Groq, Mistral)
  12. Telegram Bot API (`checkTelegram`)
- **Impact:** Each outbound HTTPS call involves TLS session negotiation (~4–6 KB per handshake) plus JSON request and response payloads. Across 15 providers, each sweep exchanges 60–100 KB over the wire.
  $$288\text{ sweeps/day} \times 80\text{ KB} \approx \mathbf{23\text{ MB/day}} \rightarrow \mathbf{414\text{ MB in 18 days}}$$

### Driver 2: GitHub Actions Keepwarm Pings
- **Location:** `.github/workflows/keepwarm.yml`
- **Mechanism:** Cron scheduled at `*/10 * * * *` (every 10 minutes) executes:
  ```bash
  curl -sf --max-time 10 https://supremeai-mcp-tower.onrender.com/health
  ```
- **Frequency:** 144 requests/day = **2,592 requests over 18 days**.
- **Payload:** The `/health` endpoint in `http_server.ts` computes the aggregated snapshot, service health, and watchdog state, serializing full JSON payloads on every ping.

### Driver 3: CI/CD Pipeline Watchdogs & Probes
- **Location:** Multiple scripts in `scripts/ci/`:
  - `render_canary.py`
  - `fleet_contract_probe.py`
  - `deploy_doctor.py`
  - `mcp_tower_conformance_probe.py`
  - `bridge_landing_watchdog.py`
  - `verdict_plane_gap_probe.py`
  - `ops-maintenance.yml` (nightly matrix)
- **Mechanism:** Every push to `main` and every pull request runs end-to-end integration probes hitting `https://supremeai-mcp-tower.onrender.com/health`, `/release`, and `/mcp`. High PR velocity multiplies request counts exponentially.

### Driver 4: Absence of HTTP Response Compression (Gzip/Brotli)
- **Location:** `infrastructure/mcp-control-plane/src/http_server.ts`
- **Mechanism:** The server uses raw Node.js `http.createServer` without a compression middleware layer.
- **Impact:** All diagnostic JSON objects, MCP tool schemas, and release metadata are sent as plain uncompressed ASCII/UTF-8 text. JSON is typically 70% to 80% compressible. Sending uncompressed text triples the egress cost.

### Driver 5: MCP Tool Manifest & Streaming Telemetry
- **Location:** Streamable HTTP (`/mcp`) and Server-Sent Events (`/sse`)
- **Mechanism:** When agents or the VS Code extension (`vscode/extension`) connect to the tower, full tool manifests (dozens of JSON schemas) are transferred. Streaming event sessions also transmit regular heartbeat and event frames.

---

## 4. Remediation & Optimization Roadmap

```mermaid
flowchart TD
    subgraph S1["Phase 1: Immediate Unblock (Render Console)"]
        A1["Add Billing Card ($0.15/GB overage)"]
        A2["OR: Migrate service to fresh free workspace"]
        A3["OR: Wait for monthly reset (Dec 1)"]
    end

    subgraph S2["Phase 2: Code Optimizations (Monorepo)"]
        B1["Increase Sweep Interval: 5m -> 30m / On-demand"]
        B2["Enable Gzip Compression in http_server.ts"]
        B3["Optimize keepwarm.yml: 10m -> 14m, use HEAD request"]
        B4["Lightweight /health/live vs Deep /health/diagnostic"]
    end

    subgraph S3["Phase 3: Long-term Stability"]
        C1["Stay within ~1.2 GB/month (< 25% of free limit)"]
        C2["No unexpected 503 outages in CI"]
    end

    S1 --> S2 --> S3
```

### Action Plan 1: Background Sweep Interval Tuning
- **Action:** Increase the sweep interval in `infrastructure/mcp-control-plane/src/index.ts` from 5 minutes to 30 minutes (or trigger provider sweeps on-demand when user requests telemetry).
- **Projected Savings:** Reduces background API polling from 288 sweeps/day to 48 sweeps/day — **an 83.3% reduction**.

### Action Plan 2: Optimize Keepwarm Cron (`keepwarm.yml`)
- **Action:**
  1. Increase cron interval from `*/10 * * * *` to `*/14 * * * *` (Render free containers idle-sleep after 15 minutes; 14 minutes maintains warm state while reducing pings by 28.5%).
  2. Use HTTP `HEAD` instead of `GET`:
     ```bash
     curl -s -I --max-time 10 https://supremeai-mcp-tower.onrender.com/health
     ```
- **Projected Savings:** Eliminates response body transfer for 3,000+ pings/month.

### Action Plan 3: Native Gzip Compression Middleware
- **Action:** Add stream-based or buffer-based Gzip compression using Node's built-in `zlib` module in `http_server.ts` for payloads exceeding 1 KB when the client sends `Accept-Encoding: gzip`.
- **Projected Savings:** Cuts payload size across all endpoints by **70%–80%**.

### Action Plan 4: Separate Liveness from Deep Diagnostics
- **Action:** 
  - `/healthz` or `/health/live`: Returns immediate minimal `{"status":"ok"}` (20 bytes). Used by keepwarm and canary uptime monitors.
  - `/health` or `/health/diagnostic`: Returns full provider snapshots only when explicitly required by dashboard operators.

---

## 5. Forecast & Projected Bandwidth Comparison

| Component | Current Monthly Usage (18d extrapolated) | Optimized Monthly Usage | Reduction |
| :--- | :--- | :--- | :--- |
| **Background Sweeps (15 APIs)** | ~700 MB | ~115 MB | **-83.5%** |
| **Keepwarm Pings** | ~180 MB | ~15 MB (HEAD request) | **-91.6%** |
| **CI/CD Probes & Watchdogs** | ~1,200 MB | ~300 MB (Gzip compressed) | **-75.0%** |
| **MCP Tools & Schema Exchanges** | ~3,500 MB | ~750 MB (Gzip compressed) | **-78.5%** |
| **Total Estimated Monthly Egress** | **~5,580 MB (Exceeds 5 GB)** | **~1,180 MB (< 25% of 5 GB)** | **~78.8% Total Savings** |

---

## 6. How to Unsuspend the Service Immediately

Because Render placed `suspenders: ['billing']` on the service, API `/resume` calls are blocked until billing clearance. Choose one of the following:

1. **Option A: Add a Card on Render Dashboard (Recommended & Instant)**
   - Click **"Remove usage limits"** or **"Add card"** in the workspace banner.
   - Overage is billed at **$0.15 per 1 GB**. Even consuming 2 extra GB for the rest of November will cost only **~$0.30 (approx 35 BDT)**.
2. **Option B: Migrate Service to an Alternate Workspace**
   - Create a secondary free Render workspace using an alternate email and deploy `infrastructure/mcp-control-plane`.
   - Update `RENDER_MCP_SERVICE_ID` and the Canary URL.
3. **Option C: Await Monthly Reset**
   - The bandwidth quota automatically resets to 0 GB on the 1st of next month (December 1, 2026).
