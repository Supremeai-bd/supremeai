#!/usr/bin/env bash
set -euo pipefail

# Separate Test Environment Setup
# Creates isolated test env with local-only Supabase/Postgres

BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TEST_DIR="$BASE_DIR/.testenv"

create_test_env() {
    echo "Creating isolated test environment at $TEST_DIR"
    mkdir -p "$TEST_DIR"
    
    cat > "$TEST_DIR/.env.test" << 'EOF'
ENV=test
DEBUG=true
JWT_SECRET=test-secret-do-not-use-in-production
OPENROUTER_API_KEY=
GEMINI_API_KEY=
SENTRY_DSN=
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=test-anon-key
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
REDIS_URL=redis://localhost:6379/0
EOF

    cat > "$TEST_DIR/docker-compose.test.yml" << 'EOF'
version: '3.8'
services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: supremeai_test
    ports:
      - "54322:5432"
    tmpfs:
      - /var/lib/postgresql/data
  redis-test:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    tmpfs:
      - /data
EOF

    echo "Test environment created."
    echo "Start with: docker-compose -f $TEST_DIR/docker-compose.test.yml up -d"
}

destroy_test_env() {
    echo "Destroying test environment..."
    docker-compose -f "$TEST_DIR/docker-compose.test.yml" down -v 2>/dev/null || true
    rm -rf "$TEST_DIR"
    echo "Test environment destroyed."
}

case "${1:-}" in
    create)
        create_test_env
        ;;
    destroy)
        destroy_test_env
        ;;
    *)
        echo "Usage: $0 {create|destroy}"
        exit 1
        ;;
esac
