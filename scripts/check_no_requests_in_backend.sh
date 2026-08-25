#!/usr/bin/env bash
# R2 FIX — CI guard: block `import requests` / `requests.X(` in backend code.
# Excludes: tests/, scripts/, examples/, pyerrorfix/detectors/ (intentional).
#
# Install in CI:
#   - script: scripts/check_no_requests_in_backend.sh
#
# Add as pre-commit hook:
#   ln -s ../../scripts/check_no_requests_in_backend.sh .git/hooks/pre-commit
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

OFFENDING_IMPORTS=$(grep -rE "^(import requests|from requests)" \
    --include='*.py' backend/ \
    --exclude-dir=tests --exclude-dir=__pycache__ \
    --exclude-dir=examples --exclude-dir=pyerrorfix \
    | grep -vE "/(test_|scripts/|pyerrorfix)" \
    | cut -d: -f1 | sort -u || true)

if [ -n "$OFFENDING_IMPORTS" ]; then
    echo "❌ BLOCKING: blocking 'requests' library found in backend code (use httpx instead):"
    echo "$OFFENDING_IMPORTS" | sed 's/^/  - /'
    echo ""
    echo "Fix: replace 'import requests' with 'import httpx' and"
    echo "     'requests.get(url, timeout=t)' with 'httpx.Client(timeout=t).get(url)'"
    echo "     or 'httpx.AsyncClient(timeout=t).get(url)' for async."
    exit 1
fi

BLOCKING_CALLS=$(grep -rE "requests\.(get|post|put|delete|patch)\(" \
    --include='*.py' backend/ \
    --exclude-dir=tests --exclude-dir=__pycache__ \
    --exclude-dir=examples --exclude-dir=pyerrorfix \
    | grep -vE "/(test_|scripts/|pyerrorfix)" || true)

if [ -n "$BLOCKING_CALLS" ]; then
    echo "❌ BLOCKING: blocking 'requests.X(' calls found in backend async routes:"
    echo "$BLOCKING_CALLS" | sed 's/^/  - /'
    exit 1
fi

echo "✅ No blocking 'requests' usage in backend code."
exit 0
