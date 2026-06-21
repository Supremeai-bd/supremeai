# Cloudflare Load Balancer & Bot Tokens Detailed Setup Guide

This guide provides step-by-step instructions for setting up the Cloudflare Workers Load Balancer and generating the API tokens for Telegram and Discord bots to complete the P0 (Critical) tasks.

---

## 1. Cloudflare Workers Load Balancer Setup

This setup enables a 3-node active-active failover routing system with weight distributions:
- **GCP Cloud Run (Primary):** 40% Weight
- **Railway Node (Secondary):** 35% Weight
- **Render Node (Fallback):** 25% Weight

### Step-by-Step Instructions:

1. **Sign Up / Log In to Cloudflare:**
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) and log in.

2. **Navigate to Workers & Pages:**
   - On the left sidebar, click on **Workers & Pages**.
   - Click the **Create Application** button.
   - Click **Create Worker**.

3. **Configure Worker Name:**
   - Set the name of your worker (e.g., `supremeai-load-balancer`).
   - Click **Deploy** (this deploys a default "Hello World" template first).

4. **Edit the Worker Code:**
   - Click **Edit Code** to open the Cloudflare Quick Edit interface.
   - Delete all placeholder code and replace it with the following implementation:

```javascript
// Weight distribution config
const BACKENDS = [
  { url: "https://supremeai-api-565236080752.us-central1.run.app", weight: 0.40 }, // GCP
  { url: "https://supremeai-api-production-c6c8.up.railway.app", weight: 0.35 },    // Railway
  { url: "https://supremeai-gzwe.onrender.com", weight: 0.25 }                      // Render
];

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
});

async function handleRequest(request) {
  const url = new URL(request.url);
  
  // 1. Choose target backend based on weight
  let random = Math.random();
  let selectedBackend = BACKENDS[0];
  let cumulativeWeight = 0;

  for (const backend of BACKENDS) {
    cumulativeWeight += backend.weight;
    if (random <= cumulativeWeight) {
      selectedBackend = backend;
      break;
    }
  }

  const targetUrl = selectedBackend.url + url.pathname + url.search;
  
  // Clone request headers & body for routing
  const modifiedRequest = new Request(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.clone().blob() : null,
    redirect: 'follow'
  });

  try {
    let response = await fetch(modifiedRequest);
    // If backend returns a server error (500+), trigger failover fallback
    if (!response.ok && response.status >= 500) {
      throw new Error(`Backend server error status: ${response.status}`);
    }
    return response;
  } catch (err) {
    console.warn(`Primary backend ${selectedBackend.url} failed. Routing to fallback... Error: ${err.message}`);
    
    // 2. Failover logic: Try all other backends sequentially
    for (const backend of BACKENDS) {
      if (backend.url === selectedBackend.url) continue;
      
      try {
        const fallbackUrl = backend.url + url.pathname + url.search;
        const fallbackRequest = new Request(fallbackUrl, {
          method: request.method,
          headers: request.headers,
          body: request.method !== 'GET' && request.method !== 'HEAD' ? await request.clone().blob() : null,
          redirect: 'follow'
        });
        
        let response = await fetch(fallbackRequest);
        if (response.ok || response.status < 500) {
          return response;
        }
      } catch (fallbackErr) {
        console.error(`Fallback backend ${backend.url} also failed:`, fallbackErr);
      }
    }
    
    return new Response(
      JSON.stringify({ error: "All multi-cloud backends are currently unreachable." }), 
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}
```

5. **Deploy the Changes:**
   - Click **Save and deploy** in the top right.
   - Copy the deployed Worker URL (e.g., `https://supremeai-load-balancer.yoursubdomain.workers.dev`).

6. **Update local configuration:**
   - Open your [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env) file.
   - Update `CLOUDFLARE_WORKER_URL` with your new worker URL.

---

## 2. Bot Tokens Setup

### A. Telegram Bot Token Setup

1. **Open Telegram Application:**
   - Search for **@BotFather** (verified account with a blue checkmark).
   
2. **Start a Conversation:**
   - Click **Start** or send `/start`.
   
3. **Create the Bot:**
   - Send the `/newbot` command.
   - Follow the prompts:
     - Enter a **Display Name** for the bot (e.g., `SupremeAI Assistant`).
     - Enter a **Username** ending in `bot` (e.g., `supreme_ai_2_bot`).
   
4. **Acquire HTTP API Token:**
   - BotFather will reply with a message containing your token key:
     `Keep your token secure and store it safely, it looks like: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`
   
5. **Configure your Env File:**
   - Copy the token and paste it into [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env):
     ```env
     TELEGRAM_BOT_TOKEN=your_token_here
     ```

---

### B. Discord Bot Token Setup

1. **Access Discord Developers Portal:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications).
   - Log in with your Discord account credentials.

2. **Create New Application:**
   - Click **New Application** in the top right.
   - Name your application (e.g., `SupremeAI Gateway`) and click **Create**.

3. **Set Up Bot Profile:**
   - Navigate to the **Bot** tab on the left menu.
   - Click **Add Bot** and confirm with "Yes, do it!".

4. **Acquire Token:**
   - Under the **Token** section, click **Reset Token** (and complete 2FA if prompted).
   - Click **Copy** to copy the generated token string. Store it safely (you won't be able to view it again without resetting).

5. **Configure Bot Permissions:**
   - Scroll down to the **Privileged Gateway Intents** section.
   - Enable **Presence Intent**, **Server Members Intent**, and **Message Content Intent** (required for bots to process text commands).
   - Save changes.

6. **Add Token to Environment:**
   - Paste the token into [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env):
     ```env
     DISCORD_BOT_TOKEN=your_token_here
     ```

7. **Generate Invite Link (Optional to join server):**
   - Go to **OAuth2** > **URL Generator** on the left menu.
   - Select the `bot` scope.
   - Under **Bot Permissions**, check `Send Messages`, `Read Message History`, `Embed Links`, etc.
   - Copy the generated URL at the bottom and open it in a browser to invite the bot to your server.

<!-- Synced with Rule Update: 2026-06-20 (Firestore Secrets and Agent Rules consolidated) -->
