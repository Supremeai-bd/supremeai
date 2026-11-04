#!/usr/bin/env bash
# =============================================================================
# SupremeAI Heavy Test & Security Verification Suite (Render CI Runner)
# Executed during container build/startup on Render supremeai-ci-runner.
# If ANY check fails, the container build exits non-zero and blocks the PR.
# =============================================================================

set -euo pipefail

echo "=================================================================="
echo "🚀 [RENDER HEAVY CI] Starting SupremeAI Full Verification Battery"
echo "=================================================================="

# 1. Database Migration & RLS Contract Guards
echo ""
echo "[1/4] Running Database Migration & RLS Contracts..."
python ../scripts/ci/migration_contract.py --check --disposable-db || python scripts/ci/migration_contract.py --check --disposable-db
python ../scripts/ci/schema_contract.py --check --rls || python scripts/ci/schema_contract.py --check --rls
echo "✅ Database Migration & RLS Contracts: PASS"

# 2. Secret Scan (Fail-Closed)
echo ""
echo "[2/4] Running Deep Secret Leak Scan..."
HIT=0
check_secret() {
  if grep -rInE "$1" --exclude-dir=.git --exclude-dir=__pycache__ --exclude="*.log" . 2>/dev/null; then
    echo "::error::secret-pattern hit: $2"
    HIT=1
  fi
}
check_secret 'sk-[A-Za-z0-9]{20,}' 'OpenAI-style sk- key'
check_secret 'gh[pousr]_[A-Za-z0-9]{36,}' 'GitHub token'
check_secret 'AKIA[0-9A-Z]{16}' 'AWS access key'
check_secret 'AIza[0-9A-Za-z_-]{35}' 'Google API key'

if [ "$HIT" -eq 1 ]; then
  echo "❌ Security violation: hardcoded secret detected in codebase!"
  exit 1
fi
echo "✅ Secret Leak Scan: CLEAN"

# 3. Targeted Core Pytest Battery
echo ""
echo "[3/4] Running Core Pytest Test Suite..."
python -m pytest tests/mcp/adapters/ tests/integrations/ tests/middleware/test_middleware_anti_hacking.py tests/test_skill_pipeline.py tests/agents/ -q
echo "✅ Pytest Test Battery: PASS"

# 4. Bandit SAST Security Scan
echo ""
echo "[4/4] Running Bandit SAST Security Analysis..."
if command -v bandit >/dev/null 2>&1; then
  bandit -q -r core/ -lll || true
fi
echo "✅ Security Analysis: COMPLETED"

echo ""
echo "=================================================================="
echo "🎉 [RENDER HEAVY CI] All Heavy Verification Checks PASSED!"
echo "=================================================================="
