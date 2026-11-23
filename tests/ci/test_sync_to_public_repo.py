# tests/ci/test_sync_to_public_repo.py
# বাংলা মন্তব্য: sync_to_public_repo.py-এর ইন্টার-রেপো সিঙ্ক্রোনাইজেশন লজিকের পূর্ণ ইউনিট টেস্ট

import json
from pathlib import Path
from scripts.ci.sync_to_public_repo import (
    sync_platform_endpoints_ts,
    sync_models_json,
    sync_security_md,
)


def test_sync_platform_endpoints_ts(tmp_path: Path):
    config_dir = tmp_path / "src" / "config"
    config_dir.mkdir(parents=True)
    target = config_dir / "platformEndpoints.ts"

    initial_content = (
        "export const DEFAULT_MCP_TOWER_ORIGIN = 'https://old-mcp.com';\n"
        "export const DEFAULT_BACKEND_ORIGIN = 'https://old-backend.com';\n"
        "export const KNOWN_RENDER_SERVICE_IDS = {\n"
        "  'supremeai-api': 'srv-old',\n"
        "};\n"
    )
    target.write_text(initial_content, encoding="utf-8")

    manifest = {
        "endpoints": {
            "api_gateway": {
                "direct_render_origin": "https://supremeai-api-ulw0.onrender.com",
                "service_id": "srv-new-api",
            },
            "mcp_tower": {
                "direct_render_origin": "https://supremeai-mcp-tower-live.onrender.com",
            },
        }
    }

    # Dry-run does not write
    changed = sync_platform_endpoints_ts(tmp_path, manifest, apply=False)
    assert changed is True
    assert target.read_text(encoding="utf-8") == initial_content

    # Apply writes new origins
    changed = sync_platform_endpoints_ts(tmp_path, manifest, apply=True)
    assert changed is True
    updated = target.read_text(encoding="utf-8")
    assert "https://supremeai-mcp-tower-live.onrender.com" in updated
    assert "https://supremeai-api-ulw0.onrender.com" in updated
    assert "'supremeai-api': 'srv-new-api'" in updated

    # Idempotent: second run without changes returns False
    changed_again = sync_platform_endpoints_ts(tmp_path, manifest, apply=True)
    assert changed_again is False


def test_sync_models_json(tmp_path: Path):
    contracts_dir = tmp_path / "packages" / "contracts"
    contracts_dir.mkdir(parents=True)
    target = contracts_dir / "models.json"

    target.write_text('{\n  "gatewayBaseUrl": "https://old-gateway.com"\n}', encoding="utf-8")

    manifest = {
        "ssot_public_gateway": "https://supremeai-studio.pages.dev/api"
    }

    # Apply updates gatewayBaseUrl
    changed = sync_models_json(tmp_path, manifest, apply=True)
    assert changed is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["gatewayBaseUrl"] == "https://supremeai-studio.pages.dev/api"

    # Idempotent
    assert sync_models_json(tmp_path, manifest, apply=True) is False


def test_sync_security_md(tmp_path: Path):
    target = tmp_path / "SECURITY.md"

    # Call sync_security_md
    changed = sync_security_md(tmp_path, apply=True)
    assert changed is True
    assert target.exists()

    content = target.read_text(encoding="utf-8")
    assert f"Supremeai-bd/{tmp_path.name}/security/advisories/new" in content
    assert "security@supremeai.com" in content

    # Idempotent
    assert sync_security_md(tmp_path, apply=True) is False
