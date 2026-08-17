# Clean Deployment Instructions

This file documents the exact deployment responsibilities for GitHub, Google Cloud, Firebase, and Supabase, plus the commands to use.

## 1. GitHub

- **What GitHub holds**: source code, documentation, CI/CD workflows, and deploy automation triggers.
- **What to do**: commit only intended changes and push to `origin main`.
- **Important**: do not push local secrets or generated build artifacts.

Example:
```bash
cd c:/Users/n/supremeai/supremeai_2.0
git add backend/.gcloudignore backend/README.md firebase.json apps/studio-client/src/App.tsx apps/studio-client/src/components/admin/AdminLogin.tsx
git commit -m "Fix deploy targets, add gcloudignore and Supabase deploy docs, restore admin shell"
git push origin main
```

## 2. Google Cloud / Cloud Run

- **What deploys here**: the backend service `supremeai-api`.
- **Source path**: `backend/`
- **Ignore rules**: `backend/.gcloudignore` keeps build context small and excludes local caches, virtual environments, local DB files, secrets, tests, and docs.
- **Runtime config**: Cloud Run must receive Supabase connection values as environment variables.

### Backend deploy commands
```bash
cd backend
gcloud auth login
gcloud config set project supremeai-a

gcloud builds submit --tag gcr.io/supremeai-a/supremeai-api .

gcloud run deploy supremeai-api \
  --image gcr.io/supremeai-a/supremeai-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="SUPABASE_URL=<your-url>,SUPABASE_KEY=<your-key>,ENV=production,GCP_PROJECT_ID=supremeai-a"
```

### Notes
- Do not upload `*.db`, `*.sqlite`, `.env*`, or `service-account.json` to Cloud Build.
- The backend code expects `SUPABASE_URL` and `SUPABASE_KEY` for Supabase.
- Optional additional runtime env vars: `SUPABASE_DATABASE_URL`, `SUPABASE_DATABASE_URL_POOLER`, `DATABASE_URL`.

## 3. Firebase Hosting

- **What deploys here**:
  - `hosting:studio` → `supremeai-a` site using `apps/web-chat/dist`
  - `hosting:admin` → `supremeai-admin` site using `apps/studio-client/dist`
- **Configuration**:
  - `firebase.json` now uses `target: "studio"` and `target: "admin"`
  - `.firebaserc` maps those targets to the correct Firebase sites

### Firebase deploy commands
```bash
cd c:/Users/n/supremeai/supremeai_2.0
firebase login
firebase use supremeai-a
firebase deploy --only hosting:admin --project supremeai-a
firebase deploy --only hosting:studio --project supremeai-a
```

### Notes
- The admin dashboard is a separate hosting target from the main studio site.
- `apps/studio-client/dist` is the admin app output.
- `apps/web-chat/dist` is the public studio app output.

## 4. Supabase

- **What Supabase is**: managed database/storage for runtime data, not a deployment target for this web app.
- **What to configure**:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - optional: `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_JWKS_URL`, `SUPABASE_DATABASE_URL`, `SUPABASE_DATABASE_URL_POOLER`, `DATABASE_URL`
- **Important**: do not try to deploy local SQLite or DB files to Supabase.

### How Supabase is used in this repo
- `backend/database/supabase_client.py` reads `SUPABASE_URL` and `SUPABASE_KEY`.
- `backend/core/config.py` may read `SUPABASE_DATABASE_URL` and related DB secrets.
- `backend/database/storage_client.py` reads `SUPABASE_URL` and `SUPABASE_KEY` for storage backup.
- `SUPABASE_PUBLISHABLE_KEY` is a frontend/public key and should not be used as the server-side secret.
- `SUPABASE_JWKS_URL` is the auth JWKS endpoint used for token verification if auth flows are enabled.
- The backend connects to Supabase at runtime when Cloud Run starts.

### Supabase setup guidance
- Create a Supabase project on https://supabase.com.
- Copy the project URL and service role/anon key.
- Store these values in Cloud Run environment variables or CI/CD secrets.
- Use the Supabase dashboard or migration scripts to create schema and seed data.

## 5. What should not be deployed

- Local files such as `*.db`, `*.sqlite`, or `data/` directories.
- Local secret files such as `service-account.json` or `.env*`.
- Build caches and IDE folders like `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.
- Generated docs and build artifacts outside the correct app dist folders.

## 6. Quick checklist

- [ ] Push only source and config changes to GitHub.
- [ ] Build backend from `backend/` with `backend/.gcloudignore` active.
- [ ] Deploy Cloud Run with Supabase env vars.
- [ ] Deploy Firebase admin and studio targets separately.
- [ ] Keep Supabase secrets out of source control.
- [ ] Use Supabase dashboard for schema and data management.

## 7. If you want the clean deploy sequence

1. `git push origin main`
2. `cd backend`
3. `gcloud builds submit --tag gcr.io/supremeai-a/supremeai-api .`
4. `gcloud run deploy supremeai-api ...`
5. `firebase deploy --only hosting:admin --project supremeai-a`
6. `firebase deploy --only hosting:studio --project supremeai-a`

This is the saved instruction set for next time. Keep this file and follow it step by step.
