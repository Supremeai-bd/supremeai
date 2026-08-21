#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
OUT="${2:-reports/gap-miner}"
python3 tools/gap_miner.py "$ROOT" --format both --out "$OUT"
python3 tools/provider_capacity_miner.py "$ROOT" --out "$OUT/provider_capacity.json"
python3 tools/security_config_miner.py "$ROOT" --out "$OUT/security_config.json"
python3 tools/architecture_miner.py "$ROOT" --out "$OUT/architecture.json"
echo "Gap mining completed: $OUT"
