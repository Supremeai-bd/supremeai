"""Contract tests for the canonical capability boundaries."""

from pathlib import Path

# বাংলা মন্তব্য: pytest CI-তে cwd `backend/` (দেখুন ci.yml: working-directory: ./backend),
# কিন্তু লোকাল ডেভে রুট থেকেও চলতে পারে -- তাই __file__ থেকে repo root বের করা হচ্ছে,
# হার্ডকোডেড "backend/..." প্রিফিক্স আর ধরে নেওয়া হচ্ছে না।
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = _REPO_ROOT / "backend"


def test_control_plane_registry_declares_all_runtime_services():
    source = (_BACKEND_ROOT / "core/service_registry.py").read_text(encoding="utf-8")
    for service in ("core-api", "async-worker", "scraper", "mcp-control-plane"):
        assert f'"{service}"' in source


def test_worker_exposes_task_lifecycle_routes():
    # বাংলা মন্তব্য: #2585 সংশোধন — পুরোনো contract মৃত ফাইল `worker_service.py` পড়ত
    # (ফাইলটি #2480 dead-file cleanup-এ ডিলিট হয়েছিল, টেস্ট হালনাগাদ হয়নি)। বর্তমান
    # সত্য: (১) task lifecycle surface `api/routes/ecosystem.py`-তে — create/read +
    # transition/deliver; (২) async-worker এখন minimal standalone consumer — Core API
    # থেকে আলাদা, CORE_API_URL fail-closed যাচাই সহ। চুক্তি বর্তমান সত্যের দিকে
    # পুনঃনির্দেশিত — টেস্ট ডিলিট নয়, অর্থবহ চুক্তি বজায়।
    ecosystem_source = (_BACKEND_ROOT / "api/routes/ecosystem.py").read_text(encoding="utf-8")
    assert '@router.post("/tasks")' in ecosystem_source
    assert '@router.get("/tasks/{task_id}")' in ecosystem_source
    assert '@router.post("/tasks/{task_id}/transition")' in ecosystem_source

    worker_source = (_BACKEND_ROOT / "services/worker/main.py").read_text(encoding="utf-8")
    assert "CORE_API_URL" in worker_source  # worker কোথাও স্বাধীন দাবি করে না — Core ভিত্তিক


def test_scraper_boundaries_apply_ssrf_validation():
    source = (_BACKEND_ROOT / "api/routes/scraper.py").read_text(encoding="utf-8")
    assert source.count("is_safe_url(request.url)") >= 2


def test_frontend_mcp_connector_uses_authenticated_client():
    # বাংলা মন্তব্য: MCPConnector.tsx এখন সরাসরি user-provided MCP endpoint-এ
    # Authorization header সহ কল করে (বা controlPlane services ব্যবহার করে)।
    # কন্ট্রাক্ট টেস্ট নিশ্চিত করে কোনো হার্ডকোডেড আনঅথেনটিকেটেড endpoint নেই এবং
    # Bearer token বা getAuthHeaders সঠিকভাবে ব্যবহৃত হচ্ছে।
    component_source = (_REPO_ROOT / "frontend/src/components/plugins/MCPConnector.tsx").read_text(
        encoding="utf-8"
    )
    viewer_source = (_REPO_ROOT / "frontend/src/services/mcpViewer.ts").read_text(encoding="utf-8")
    service_source = (_REPO_ROOT / "frontend/src/services/controlPlane.ts").read_text(
        encoding="utf-8"
    )
    assert "Authorization: `Bearer ${token.trim()}`" in viewer_source
    assert "loadMcpViewerData" in component_source
    assert "fetch('/api/v1/mcp/discover'" not in component_source
    assert "fetch('/api/v1/mcp/discover'" not in service_source
    assert "any[]" not in component_source
    assert "any[]" not in service_source
    assert "getAuthHeaders" in service_source
    for helper in (
        "async function getJson",
        "async function postJson",
        "async function deleteJson",
    ):
        assert helper in service_source
    assert "revokeExternalClient: (id: string) => deleteJson" in service_source
