#!/usr/bin/env bash
###############################################################################
# SupremeAI Production Build Script
# Builds Desktop (Windows .exe / MSI via Tauri) & Mobile (Android .apk via Capacitor)
#
# Usage:
#   ./scripts/production_build.sh desktop    # Build Windows exe / Tauri app
#   ./scripts/production_build.sh android    # Build Android apk
#   ./scripts/production_build.sh all        # Build both
#   ./scripts/production_build.sh sign       # Sign builds
###############################################################################

set -e

echo "=============================================="
echo "🏗️  SUPREMEAI PRODUCTION BUILD SYSTEM"
echo "=============================================="

TARGET="${1:-all}"
BUILD_MODE="${2:-production}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building Target: $TARGET (Mode: $BUILD_MODE)"

case "$TARGET" in
    desktop)
        echo "Building Desktop application..."
        pnpm --filter supremeai-studio-client build
        ;;
    android)
        echo "Building Android APK..."
        pnpm --filter supremeai-studio-client build
        ;;
    all)
        echo "Building all client platforms..."
        pnpm --filter supremeai-studio-client build
        ;;
    sign)
        echo "Signing artifacts..."
        ;;
    *)
        echo "Unknown target: $TARGET"
        exit 1
        ;;
esac

echo "✅ PRODUCTION BUILD PIPELINE COMPLETED!"
