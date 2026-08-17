# Multi-Platform Frontend & Backend Failover Strategy

SupremeAI 2.0 uses a highly resilient, **Zero-Cost Multi-Cloud Architecture**. To ensure 100% uptime without paying for premium tiers, we combine multiple free-tier services (Vercel, Netlify, Firebase, Render) into a cohesive, self-healing network.

## 1. The Strategy: "Hydra Architecture"

Like a Hydra, if one platform blocks us (e.g., Vercel's 100 deploys/day limit) or goes to sleep (Render's inactivity sleep), another head immediately takes over.

We achieve this by fully separating our Frontend Hosting from our Backend compute, and embedding a **Client-Side Load Balancer** directly into the frontend.

### Frontend Hosting (Vercel + Netlify + Firebase)
Instead of relying on a single hosting provider, our Vite React frontend is fully agnostic.
- **Vercel:** Primary testing/staging environment.
- **Netlify:** Automatic failover for CI/CD when Vercel limits are hit.
- **Firebase Hosting:** The ultimate production CDN (as outlined in `AGENTS.md`).

Because we use standard tools (`netlify.toml`, `vercel.json`, and `firebase.json`), the exact same code can be pushed to all three platforms simultaneously. If Vercel goes down or blocks a deployment, the Netlify URL remains live.

### Backend APIs (Dual Render Strategy)
Free Render instances sleep after 15 minutes of inactivity. To fix this without paying $7/month:
1. **Primary Server:** `supremeai-backend-08zd.onrender.com`
2. **Secondary Server:** `supremeai-backend-secondary.onrender.com`

## 2. How the Client-Side Interceptor Works (The Magic)

We don't use a traditional paid Load Balancer (like AWS ELB). Instead, the user's browser acts as the load balancer!

1. **Anti-Sleep Heartbeat (`heartbeat.ts`):**
   When a user opens the web app, the browser silently pings both the Primary and Secondary Render servers every 10 minutes. This prevents the active servers from ever going to sleep while a user is online.
2. **Smart Failover (`apiClient.ts`):**
   If a server is asleep or restarting, it returns a 502, 503, or 504 error. When the frontend `fetch` interceptor detects this:
   - It intercepts the error before the user notices.
   - It calls `switchActiveBackend()` (in `api.ts`) to instantly swap to the Secondary Server.
   - It waits 1 second, rewrites the URL, and retries the API call.
   - The user experiences a 1-second delay instead of a broken app.

## 3. Workflow Example: "A Day in the Life"

1. Developer pushes a commit to `main`.
2. GitHub Actions triggers deployments to both **Vercel** and **Netlify**.
3. **Vercel** throws a "100 limit reached" error and fails.
4. **Netlify** succeeds. The team uses the Netlify URL for the rest of the day.
5. A user visits the Netlify URL.
6. The user clicks "Login". The frontend sends a request to the Primary Render server.
7. The Primary server is sleeping (returns 502).
8. The frontend intercepts the 502, silently switches to the Secondary Render server, and retries.
9. The Secondary server responds successfully. The user logs in seamlessly.
10. The browser starts sending background "Heartbeats" every 10 minutes to keep both servers awake.

## 4. Environment Synchronization (Important!)

Because requests can seamlessly bounce between platforms, **all platforms must be identical**:
- You must keep the exact same `.env` variables (e.g., `JWT_SECRET`, database keys) in the Render dashboards for both Primary and Secondary backends.
- You do not need to hardcode API URLs in Vercel or Netlify. The `api.ts` file dynamically manages the fallback array `RENDER_BACKENDS`.

---
*By combining the free tiers of Firebase, Vercel, Netlify, and Render, SupremeAI achieves enterprise-grade High Availability for $0/month.*
