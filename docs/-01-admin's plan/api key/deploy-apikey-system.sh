#!/bin/bash
# SupremeAI 2.0 — API Key System Deployment Script
# Usage: ./deploy-apikey-system.sh [environment]

set -e

ENV=${1:-staging}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying API Key Management System to $ENV"

# ═══════════════════════════════════════════════════════════════
# STEP 1: Database Migration
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 1: Running database migrations..."
cd "$PROJECT_ROOT/backend"

# Create migration
poetry run alembic revision --autogenerate -m "add_api_key_management_tables"

# Run migration
poetry run alembic upgrade head

# Verify migration
poetry run alembic current

echo "✅ Database migration complete"

# ═══════════════════════════════════════════════════════════════
# STEP 2: Install Redis (if not already installed)
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 2: Checking Redis..."
if ! command -v redis-cli &> /dev/null; then
    echo "Installing Redis..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y redis-server
        sudo systemctl enable redis-server
        sudo systemctl start redis-server
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install redis
        brew services start redis
    fi
fi

# Test Redis connection
redis-cli ping || (echo "❌ Redis is not running" && exit 1)
echo "✅ Redis is ready"

# ═══════════════════════════════════════════════════════════════
# STEP 3: Update Environment Variables
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 3: Updating environment configuration..."

ENV_FILE="$PROJECT_ROOT/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# Add required env vars if not present
if ! grep -q "REDIS_URL" "$ENV_FILE"; then
    echo "REDIS_URL=redis://localhost:6379/0" >> "$ENV_FILE"
fi

if ! grep -q "API_KEY_HASH_ROUNDS" "$ENV_FILE"; then
    echo "API_KEY_HASH_ROUNDS=12" >> "$ENV_FILE"
fi

if ! grep -q "API_KEY_MAX_AGE_DAYS" "$ENV_FILE"; then
    echo "API_KEY_MAX_AGE_DAYS=90" >> "$ENV_FILE"
fi

echo "✅ Environment configuration updated"

# ═══════════════════════════════════════════════════════════════
# STEP 4: Install Dependencies
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 4: Installing dependencies..."
cd "$PROJECT_ROOT/backend"
poetry install --with dev

# Install Redis client
poetry add redis[hiredis] bcrypt

echo "✅ Dependencies installed"

# ═══════════════════════════════════════════════════════════════
# STEP 5: Run Tests
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 5: Running tests..."
poetry run pytest tests/api/test_keys.py -v --tb=short

echo "✅ Tests passed"

# ═══════════════════════════════════════════════════════════════
# STEP 6: Deploy to Cloud Run (Production) or Docker (Staging)
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 6: Deploying application..."

if [ "$ENV" == "production" ]; then
    # Production: Cloud Run
    echo "Deploying to Cloud Run..."
    cd "$PROJECT_ROOT"
    gcloud run deploy supremeai-api         --source .         --region us-central1         --allow-unauthenticated         --set-env-vars "ENV=production,REDIS_URL=${REDIS_URL}"

    # Deploy Celery workers
    gcloud run deploy supremeai-celery         --source .         --region us-central1         --no-allow-unauthenticated         --set-env-vars "ENV=production,REDIS_URL=${REDIS_URL}"

else
    # Staging: Docker Compose
    echo "Deploying with Docker Compose..."
    cd "$PROJECT_ROOT"
    docker-compose -f docker-compose.yml up -d --build api redis celery
fi

echo "✅ Deployment complete"

# ═══════════════════════════════════════════════════════════════
# STEP 7: Verify Deployment
# ═══════════════════════════════════════════════════════════════
echo "📦 Step 7: Verifying deployment..."

# Health check
HEALTH_URL="http://localhost:8000/health"
if [ "$ENV" == "production" ]; then
    HEALTH_URL="https://api.supremeai.dev/health"
fi

for i in {1..10}; do
    if curl -s "$HEALTH_URL" | grep -q "ok"; then
        echo "✅ Health check passed"
        break
    fi
    echo "Waiting for health check... ($i/10)"
    sleep 5
done

echo ""
echo "🎉 API Key Management System deployed successfully!"
echo ""
echo "Next steps:"
echo "  1. Test key creation: curl -X POST http://localhost:8000/api/v1/keys"
echo "  2. Verify rate limiting: curl -H 'Authorization: Bearer <key>' http://localhost:8000/api/v1/inference"
echo "  3. Monitor Redis: redis-cli monitor"
echo "  4. Check Celery: celery -A tasks flower"
