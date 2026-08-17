#!/usr/bin/env bash
# Smart Build Script for SupremeAI Frontend (Self-Healing)

echo "==========================================="
echo "🚀 Starting Smart Build for Frontend..."
echo "==========================================="

echo "📦 Installing pnpm..."
npm install -g pnpm@9

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

echo "🏗️ Building frontend..."
cd frontend && pnpm run build:user

echo "🎉 Frontend build finished successfully!"
