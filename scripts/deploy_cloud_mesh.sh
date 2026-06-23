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

if command -v railway >/dev/null 2>&1; then
  railway up --detach
fi

if command -v renderctl >/dev/null 2>&1; then
  renderctl deploy
fi

if command -v wrangler >/dev/null 2>&1; then
  wrangler deploy infrastructure/cloudflare/worker.js --config infrastructure/cloudflare/wrangler.toml
fi
