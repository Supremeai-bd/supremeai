"""Regression tests for the free-tier 5 GB bandwidth & polling CI guard."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import check_free_tier_limits as guard


def _seed_safe_tree(base: Path) -> None:
    mcp_src = base / "infrastructure" / "mcp-control-plane" / "src"
    (mcp_src / "health").mkdir(parents=True, exist_ok=True)
    (base / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

    (mcp_src / "index.ts").write_text(
        "const sweepIntervalMs = 8 * 60 * 1000;\n"
        "setInterval(() => {\n"
        "  globalHealthEngine.runFullSweep().catch((e) => console.error(e));\n"
        "}, sweepIntervalMs);\n",
        encoding="utf-8",
    )
    (mcp_src / "health" / "engine.ts").write_text(
        "export const OPTIONAL_PROVIDER_TTL_MS = 60 * 60 * 1000;\n",
        encoding="utf-8",
    )
    (mcp_src / "http_server.ts").write_text(
        'import { gzipSync } from "node:zlib";\n'
        'res.writeHead(200, { "Content-Encoding": "gzip" });\n',
        encoding="utf-8",
    )
    (base / ".github" / "workflows" / "keepwarm.yml").write_text(
        "on:\n  schedule:\n    # replaced */10 * * * *\n    - cron: '0 */6 * * *'\n",
        encoding="utf-8",
    )


def test_repo_passes_bandwidth_and_polling_guard() -> None:
    assert guard.check_bandwidth_and_polling_guard(ROOT) is False


def test_blocks_aggressive_sweep_interval(tmp_path: Path) -> None:
    _seed_safe_tree(tmp_path)
    index_ts = tmp_path / "infrastructure" / "mcp-control-plane" / "src" / "index.ts"
    index_ts.write_text(
        "setInterval(() => {\n"
        "  globalHealthEngine.runFullSweep().catch((e) => console.error(e));\n"
        "}, 60 * 1000);\n",
        encoding="utf-8",
    )
    assert guard.check_bandwidth_and_polling_guard(tmp_path) is True


def test_blocks_missing_optional_provider_ttl(tmp_path: Path) -> None:
    _seed_safe_tree(tmp_path)
    engine_ts = tmp_path / "infrastructure" / "mcp-control-plane" / "src" / "health" / "engine.ts"
    engine_ts.write_text("export const CHECK_TIMEOUT_MS = 15000;\n", encoding="utf-8")
    assert guard.check_bandwidth_and_polling_guard(tmp_path) is True


def test_blocks_missing_gzip_compression(tmp_path: Path) -> None:
    _seed_safe_tree(tmp_path)
    http_ts = tmp_path / "infrastructure" / "mcp-control-plane" / "src" / "http_server.ts"
    http_ts.write_text("res.end(JSON.stringify({ ok: true }));\n", encoding="utf-8")
    assert guard.check_bandwidth_and_polling_guard(tmp_path) is True


def test_blocks_duplicate_high_freq_keepwarm_cron(tmp_path: Path) -> None:
    _seed_safe_tree(tmp_path)
    kw = tmp_path / ".github" / "workflows" / "keepwarm.yml"
    kw.write_text("on:\n  schedule:\n    - cron: '*/10 * * * *'\n", encoding="utf-8")
    assert guard.check_bandwidth_and_polling_guard(tmp_path) is True


def test_worker_advertises_configured_cron():
    worker = ROOT / "infrastructure" / "cloudflare-render-keepwarm"
    cron, = tomllib.loads((worker / "wrangler.toml").read_text())["triggers"]["crons"]
    assert f'schedule: "{cron}"' in (worker / "worker.js").read_text()
