#!/bin/bash
# ============================================================================
# script >> deploy_cloud_mesh.sh
# project >> SupremeAI 2.0
# purpose >> Cloud provider
# module >> scripts
# ============================================================================
if command -v gcloud >/dev/null 2>&1; then
  gcloud run deploy "${SERVICE}" --image "${IMAGE}" --region "${GCP_REGION}" --project "${PROJECT_ID}"
fi

if command -v railway >/dev/null 2>&1; then
  railway up --detach
fi

if command -v renderctl >/dev/null 2>&1; then
  renderctl deploy
fi

if command -v wrangler >/dev/null 2>&1; then
  wrangler deploy infrastructure/cloudflare/worker.js --config infrastructure/cloudflare/wrangler.toml
fi
