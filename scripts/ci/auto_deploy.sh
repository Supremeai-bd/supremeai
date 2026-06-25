#!/bin/bash
# scripts/ci/auto_deploy.sh
# Auto-deploy script for SupremeAI 2.0 to Google Cloud Run

set -euo pipefail

echo "🚀 Starting auto-deployment of SupremeAI 2.0 to Cloud Run..."

# Check if required environment variables are set
if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  echo "❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set"
  exit 1
fi

if [[ -z "${CLOUD_RUN_SERVICE:-}" ]]; then
  echo "❌ Error: CLOUD_RUN_SERVICE environment variable is not set"
  exit 1
fi

# Build and deploy the backend
echo "📦 Building and deploying backend service..."
cd backend
poetry export -f requirements.txt --output requirements.txt --without-hashes
gcloud run deploy "${CLOUD_RUN_SERVICE}-backend" \
  --source . \
  --platform managed \
  --region "${CLOUD_RUN_REGION:-us-central1}" \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --allow-unauthenticated \
  --max-instances "${MAX_INSTANCES:-10}" \
  --cpu "${CPU_LIMIT:-1}" \
  --memory "${MEMORY:-512Mi}" \
  --set-env-vars="ENVIRONMENT=production"

# Deploy frontend (if applicable)
echo "🎨 Deploying frontend..."
cd ../apps/studio-client
npm ci
npm run build
firebase hosting:channel:deploy ci \
  --project "${FIREBASE_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}" \
  --expire 7d

# Deploy mobile app (if applicable)
echo "📱 Deploying mobile app..."
cd ../../apps/mobile
flutter build apk --release
# In a real scenario, you would upload to Firebase App Distribution or Google Play
echo "✅ Mobile APK built successfully"

echo "✅ Deployment completed successfully!"