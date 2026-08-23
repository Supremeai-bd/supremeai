#!/usr/bin/env bash
# Smart Build Script for SupremeAI Frontend (Self-Healing + Dynamic Config)
# 🔧 ADDED: Build-time placeholder replacement for firebase.json

echo "==========================================="
echo "🚀 Starting Smart Build for Frontend..."
echo "==========================================="

echo "📦 Installing pnpm..."
npm install -g pnpm

echo "📦 Attempting to install monorepo dependencies..."
# Disable exit-on-error temporarily to catch failures
set +e

pnpm install --no-frozen-lockfile
EXIT_CODE=$?

# Re-enable exit-on-error
set -e

if [ $EXIT_CODE -ne 0 ]; then
    echo "⚠️ Dependency installation failed with exit code $EXIT_CODE!"
    echo "🧹 Possible corrupted cache detected. Clearing node_modules..."
    
    # Remove node_modules at root and inside frontend
    rm -rf node_modules
    rm -rf frontend/node_modules
    
    # Remove pnpm store cache if it exists locally
    pnpm store prune || true
    
    echo "🔄 Retrying clean installation..."
    pnpm install --no-frozen-lockfile
else
    echo "✅ Frontend dependencies installed successfully."
fi

# 🔬 Evolution v3.0: Pre-build validation
echo "🔬 Running pre-build validation..."

# Check for required files
REQUIRED_FILES=("frontend/vite.config.ts" "frontend/package.json" "frontend/tsconfig.json")
for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "❌ ERROR: Required file missing: $file"
    exit 1
  fi
done

# Validate backend URL format (must be https://)
if [ -n "$VITE_ADMIN_BACKEND" ] && [[ ! "$VITE_ADMIN_BACKEND" =~ ^https?:// ]]; then
  echo "❌ ERROR: VITE_ADMIN_BACKEND must be a valid URL (starting with http:// or https://)"
  exit 1
fi


echo "🔧 Checking for required environment variables..."
if [ -z "$VITE_ADMIN_BACKEND" ] && [ "$VITE_PORTAL_TYPE" = "admin" ]; then
  echo "⚠️ WARNING: VITE_ADMIN_BACKEND not set! Using RENDER_EXTERNAL_HOSTNAME fallback."
  export VITE_ADMIN_BACKEND="https://${RENDER_EXTERNAL_HOSTNAME:-supremeai-backend-docker}.onrender.com"
  echo "VITE_ADMIN_BACKEND=$VITE_ADMIN_BACKEND" >> frontend/.env.local
fi

if [ -z "$VITE_USER_BACKEND" ] && [ "$VITE_PORTAL_TYPE" != "admin" ]; then
  echo "⚠️ WARNING: VITE_USER_BACKEND not set! Using RENDER_EXTERNAL_HOSTNAME fallback."
  export VITE_USER_BACKEND="https://${RENDER_EXTERNAL_HOSTNAME:-supremeai-backend-docker}.onrender.com"
  echo "VITE_USER_BACKEND=$VITE_USER_BACKEND" >> frontend/.env.local
fi

echo "🏗️ Building frontend..."
cd frontend && pnpm run build:user
cd ..

echo "🔧 Replacing placeholders in firebase.json..."
BACKEND_URL="${VITE_ADMIN_BACKEND:-${VITE_USER_BACKEND}}"
find . -name "firebase.json" -exec sed -i "s|{{BACKEND_URL}}|${BACKEND_URL}|g" {} \; 2>/dev/null || true
echo "✅ Firebase rewrites updated with backend URL: ${BACKEND_URL}"

# 🔬 Evolution v3.0: Post-build verification
echo "🔬 Running post-build verification..."

if [ ! -d "frontend/dist-user" ] && [ ! -d "frontend/dist-admin" ]; then
  echo "❌ ERROR: Build output directory missing!"
  exit 1
fi

# Verify build-info.json was created (if production)
if [ "$NODE_ENV" = "production" ] && [ ! -f "frontend/dist-user/build-info.json" ] && [ ! -f "frontend/dist-admin/build-info.json" ]; then
  echo "❌ ERROR: build-info.json was not generated in production build!"
  exit 1
fi

echo "🎉 Frontend build finished successfully!"
