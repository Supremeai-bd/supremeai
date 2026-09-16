#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-supremeai}"
IMAGE="${IMAGE:-${PROJECT_ID}/supremeai:${GITHUB_SHA:-local}}"
GCP_REGION="${GCP_REGION:-${REGION}}"

if command -v docker >/dev/null 2>&1; then
  docker build -t "${IMAGE}" .
fi

if command -v gcloud >/dev/null 2>&1; then
  gcloud run deploy "${SERVICE}" --image "${IMAGE}" --region "${GCP_REGION}" --project "${PROJECT_ID}"
fi


if command -v wrangler >/dev/null 2>&1; then
  # No positional script path: wrangler.toml `main = "enhanced-worker.js"` is the
  # single source of truth. Passing "worker.js" here used to OVERRIDE main and
  # silently deploy the 76-line static-asset stub instead of the real
  # multi-node failover + edge-cache worker.
  wrangler deploy --config infrastructure/cloudflare/wrangler.toml
fi
