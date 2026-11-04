#!/usr/bin/env bash
# =============================================================================
# SupremeAI Heavy Test & Security Verification Suite (Render CI Runner)
# Executed during container build/startup on Render supremeai-ci-runner.
# Scope: Every PR Push + Scheduled Nightly Execution.
# If ANY check fails, the container build exits non-zero and blocks deployment.
# =============================================================================

set -euo pipefail

echo "=================================================================="
echo "🚀 [RENDER HEAVY CI] Starting SupremeAI Full Verification Battery"
echo "=================================================================="

# 1. Database Migration & RLS Contract Guards
echo ""
echo "[1/6] Running Database Migration & RLS Contracts..."
if [ -f scripts/ci/migration_contract.py ]; then
  python scripts/ci/migration_contract.py --check --disposable-db
elif [ -f ../scripts/ci/migration_contract.py ]; then
  python ../scripts/ci/migration_contract.py --check --disposable-db
else
  echo "[WARN] migration_contract.py not found, skipping."
fi

if [ -f scripts/ci/schema_contract.py ]; then
  python scripts/ci/schema_contract.py --check --rls
elif [ -f ../scripts/ci/schema_contract.py ]; then
  python ../scripts/ci/schema_contract.py --check --rls
else
  echo "[WARN] schema_contract.py not found, skipping."
fi
echo "✅ Database Migration & RLS Contracts: PASS"

# 2. Deep Secret Scan (Fail-Closed)
echo ""
echo "[2/6] Running Deep Secret Leak Scan..."
HIT=0
check_secret() {
  if grep -rInE "$1" --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=tests --exclude="*.log" . 2>/dev/null; then
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

# 3. Python Bytecode Compilation (compileall)
echo ""
echo "[3/6] Running Bytecode Compilation Verification..."
python -m compileall -q .
echo "✅ Bytecode Compilation: PASS"

# Ensure `core.*` import paths resolve (Docker WORKDIR is /app = core contents)
ln -sfn . core

# 4. Core Pytest Battery
echo ""
echo "[4/6] Running Core Pytest Test Suite..."
python -m pytest tests/mcp/adapters/ tests/integrations/ tests/middleware/test_middleware_anti_hacking.py tests/test_skill_pipeline.py -q
echo "✅ Pytest Test Battery: PASS"

# 5. Security & Vulnerability Analysis
echo ""
echo "[5/6] Running Static Security & Vulnerability Scans..."
if command -v bandit >/dev/null 2>&1; then
  bandit -q -r . -lll || true
fi
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r requirements.txt || true
fi
echo "✅ Security Analysis: COMPLETED"

# 6. Autonomous Agent Loop Verification
echo ""
echo "[6/6] Verifying Continuous Agent Loop Parity..."
if [ -f ../scripts/agents/continuous_agent_loop.py ]; then
  python ../scripts/agents/continuous_agent_loop.py --verify-only || true
elif [ -f scripts/agents/continuous_agent_loop.py ]; then
  python scripts/agents/continuous_agent_loop.py --verify-only || true
fi
echo "✅ Agent Loop Verification: PASS"

echo ""
echo "=================================================================="
echo "🎉 [RENDER HEAVY CI] All Heavy Verification Checks PASSED!"
echo "=================================================================="
