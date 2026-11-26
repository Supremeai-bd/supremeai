#!/usr/bin/env bash
# বাংলা মন্তব্য: A5 — ৩-স্তর ভেরিফিকেশন (Reflection, Boot Smoke, Pytest) চালিয়ে PR-এর Test Evidence তৈরি করে
set -euo pipefail

echo "## Test Evidence"
echo ""
echo "### 1. Boot Smoke"
if python3 -c "import core.main; print('boot_smoke: OK')" 2>&1; then
  echo "- Boot smoke: PASS"
else
  echo "- Boot smoke: FAIL"
fi

echo ""
echo "### 2. Pytest (Targeted)"
if [ $# -gt 0 ]; then
  pytest "$@" -q --tb=short 2>&1 | tail -n 20
else
  pytest tests/test_guard_inventory.py -q --tb=short 2>&1 | tail -n 10
fi
