# Frontend Deployment Guide (Vercel, Netlify, Firebase)

This document contains step-by-step instructions for deploying the `supremeai-studio-client` frontend to various free-tier hosting providers.

## 1. Firebase Hosting (Recommended)

As per the `AGENTS.md` zero-cost architecture, Firebase Hosting is the primary recommended platform for deploying the frontend.

### Configuration Steps
1. Make sure you have the Firebase CLI installed: `npm install -g firebase-tools`
2. Run `firebase login` to authenticate.
3. In the root of the project, run `firebase init hosting`.
4. Answer the prompts as follows:
   - **What do you want to use as your public directory?** `apps/studio-client/dist-user`
   - **Configure as a single-page app (rewrite all urls to /index.html)?** `Yes`
   - **Set up automatic builds and deploys with GitHub?** `Yes` (if you want CI/CD).
5. Deploy manually: `firebase deploy --only hosting`.

---

## 2. Vercel

Vercel is great for React/Vite apps but has a strict daily deployment limit on the Hobby tier (100 deployments per day).

### Configuration Steps
1. Go to the Vercel Dashboard and click **Add New... > Project**.
2. Import the GitHub repository for SupremeAI.
3. Configure the **Build & Deployment Settings**:
   - **Framework Preset:** `Vite` (or `Other`)
   - **Root Directory:** `apps/studio-client`
   - **Build Command:** `turbo run build` (Override enabled)
   - **Output Directory:** `dist-user` (Override enabled)
   - **Install Command:** `pnpm install` (Override enabled)
4. We have a `apps/studio-client/vercel.json` file that handles the SPA routing (all requests to `index.html`).
5. **Important:** If you encounter `404 NOT_FOUND`, make sure the **Output Directory** is explicitly set to `dist-user`.

---

## 3. Netlify

Netlify is a robust alternative with very generous limits and fast global CDN.

### Configuration Steps
1. Go to Netlify Dashboard and click **Add new site > Import an existing project**.
2. Select **GitHub** and authorize access to your repository.
3. Netlify will automatically detect our `netlify.toml` file in the root directory.
4. You do not need to configure anything manually! The `netlify.toml` file handles:
   - Base directory: `apps/studio-client`
   - Build command: `pnpm install && turbo run build`
   - Publish directory: `dist-user`
   - SPA Routing: `/*` -> `/index.html` (Status 200)
5. Just click **Deploy site**.

### Need to switch platforms?
Because of our intelligent `switchActiveBackend()` failover system and standard Vite build setup, you can switch between Vercel, Netlify, and Firebase at any time without changing any frontend application code. Just ensure the Environment Variables (`VITE_API_BASE`, etc.) are configured in your chosen platform's dashboard if they differ from the defaults.
