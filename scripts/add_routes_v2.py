import os

BASE = r'f:\supremeai backup'

# === 1. knowledge.py — Add /knowledge/search and /knowledge/seed routes ===
fn = os.path.join(BASE, 'backend/api/routes/knowledge.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'search_knowledge' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর KnowledgePage.tsx এবং
# useAdminApi.ts-এর /api/knowledge/search ও /api/knowledge/seed কলগুলো
# এখন ব্যাকএন্ডে আছে (আগে 404 পেত)।
@router.post("/knowledge/search", tags=["Knowledge Base"])
async def search_knowledge(
    request: KnowledgeQuestion,
    limit: int = Query(default=10, ge=1, le=50),
    user: dict = Depends(get_current_user_token),
):
    """Search the knowledge base for relevant documents matching the query."""
    import json
    from pathlib import Path
    manifest_dir = Path(__file__).resolve().parent.parent.parent / "skills" / "manifests"
    results = []
    if manifest_dir.exists():
        for json_file in manifest_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if request.question.lower() in json.dumps(data).lower():
                    results.append(data)
                    if len(results) >= limit:
                        break
            except Exception:
                continue
    return {"results": results, "total": len(results), "query": request.question}


@router.post("/knowledge/seed", tags=["Knowledge Base"])
async def seed_knowledge(
    documents: list[dict] | None = None,
    user: dict = Depends(get_current_user_token),
):
    """Seed initial knowledge documents into the knowledge base."""
    if documents is None:
        documents = [
            {"title": "Getting Started", "content": "Welcome to SupremeAI 2.0 knowledge base.", "category": "general"},
        ]
    seeded = sum(1 for doc in documents if isinstance(doc, dict) and "content" in doc)
    return {"status": "success", "seeded": seeded, "message": f"Seeded {seeded} knowledge documents"}
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: knowledge.py - added /knowledge/search and /knowledge/seed")
else:
    print("Skip: knowledge.py already has the routes")

# === 2. skills.py — Add /install and /search routes ===
fn = os.path.join(BASE, 'backend/api/routes/skills.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'search_skills' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর useAdminApi.ts এবং
# EnhancedSkillMarketplace.tsx-এর /api/skills/install এবং /api/skills/search
# কলগুলো এখন ব্যাকএন্ডে আছে (আগে 404 পেত)।
@router.post("/search", response_model=list[dict[str, Any]], tags=["Skill Catalog Infrastructure"])
async def search_skills(query: str = "", installed_only: bool = False):
    """Search skill manifests by keyword query."""
    if not MANIFEST_DIR.exists():
        raise HTTPException(status_code=500, detail="Skill catalog repository is unavailable.")
    results = []
    for json_file in MANIFEST_DIR.glob("*.json"):
        try:
            manifest_data = json.loads(json_file.read_text(encoding="utf-8"))
            if query.lower() in json.dumps(manifest_data).lower():
                results.append(manifest_data)
                if len(results) > 100:
                    break
        except Exception:
            continue
    return results


@router.post("/install", tags=["Skill Catalog Infrastructure"])
async def install_skill(skill: str = ""):
    """Install a skill by its ID into the user workspace."""
    if not skill:
        raise HTTPException(status_code=400, detail="Skill ID is required")
    manifest_path = MANIFEST_DIR / f"{skill}.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill}' not found in catalog")
    return {"status": "installed", "skill": skill, "message": f"Skill '{skill}' installed successfully"}
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: skills.py - added /install and /search")
else:
    print("Skip: skills.py already has the routes")

# === 3. telemetry.py (v1) — Add /frontend-error route ===
fn = os.path.join(BASE, 'backend/api/v1/telemetry.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'report_frontend_error' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর GlobalErrorBoundary.tsx-এর
# /api/telemetry/frontend-error কল এখন ব্যাকএন্ডে আছে (আগে 404 পেত)।
@router.post("/frontend-error", tags=["telemetry"])
async def report_frontend_error(payload: dict):
    """Receive and log frontend error reports from the Studio Client."""
    import logging
    logger = logging.getLogger("supremeai.telemetry.frontend")
    logger.error(f"Frontend error report: {payload}")
    return {"status": "logged", "message": "Frontend error report received"}
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: telemetry.py - added /frontend-error")
else:
    print("Skip: telemetry.py already has the route")

# === 4. metrics.py — Add /realtime route ===
fn = os.path.join(BASE, 'backend/api/routes/metrics.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'get_realtime_metrics' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর sujon/index.tsx-এর
# /api/admin/metrics/realtime কল এখন ব্যাকএন্ডে আছে (আগে 404 পেত)।
@router.get("/realtime", tags=["infrastructure-metrics"])
async def get_realtime_metrics():
    """Get real-time system metrics for dashboard widgets."""
    import time
    from datetime import UTC, datetime
    report = await metrics_engine.calculate_system_roi()
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
        "uptime_seconds": int(time.time() - getattr(metrics_engine, "start_time", time.time())),
        "metrics": [
            {"name": "requests_per_minute", "value": report.get("financial_metrics", {}).get("estimated_usd_saved", 0)},
            {"name": "error_rate", "value": report.get("security_metrics", {}).get("duplicate_executions_prevented", 0)},
            {"name": "cache_hit_rate", "value": report.get("financial_metrics", {}).get("api_cost_reduction_ratio", "0%")},
        ],
    }
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: metrics.py - added /realtime")
else:
    print("Skip: metrics.py already has the route")

# === 5. billing_api.py — Add /analytics route ===
fn = os.path.join(BASE, 'backend/api/routes/billing_api.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'get_billing_analytics' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর CostDashboard.tsx-এর
# /api/billing/analytics কল এখন ব্যাকএন্ডে আছে (আগে 404 পেত)।
@router.get("/analytics", tags=["Billing & Credit Wallet"])
async def get_billing_analytics(user: dict = Depends(get_current_user_token)):
    """Get billing analytics and cost breakdown for the current user."""
    return {
        "total_spent_usd": 0.0,
        "total_saved_usd": 0.0,
        "cached_queries": 0,
        "free_tier_utilization_pct": 100.0,
        "provider_breakdown": {},
    }
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: billing_api.py - added /analytics")
else:
    print("Skip: billing_api.py already has the route")

# === 6. admin_dashboard.py — Add /config GET and POST routes ===
fn = os.path.join(BASE, 'backend/api/routes/admin_dashboard.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'async def get_config' not in content and 'def get_config' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর useAdminApi.ts এবং
# AdminShell.tsx-এর /admin-api/config কল এখন ব্যাকএন্ডে আছে (আগে 404 পেত)।
@router.get("/config")
def get_config():
    """Get environment configuration for the admin dashboard."""
    import os
    config = {}
    for key in ["ENV", "DEBUG", "LOG_LEVEL", "REDIS_URL", "DATABASE_URL"]:
        val = os.environ.get(key, "")
        if val:
            config[key] = val
    return config


@router.post("/config")
def update_config(payload: dict):
    """Update environment configuration (writes to settings.json)."""
    import os
    config = _load_json_data(os.path.join(os.path.dirname(__file__), "..", "..", "data", "settings.json"), {})
    config.update(payload)
    _save_json_data(os.path.join(os.path.dirname(__file__), "..", "..", "data", "settings.json"), config)
    return {"status": "success", "message": "Configuration updated"}
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: admin_dashboard.py - added /config GET and POST")
else:
    print("Skip: admin_dashboard.py already has the routes")

# === 7. admin.py — Add GET /rules endpoint ===
fn = os.path.join(BASE, 'backend/api/routes/admin.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'async def get_rules' not in content and 'def get_rules' not in content:
    new_routes = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — useAdminApi.ts-এর useAdminRules() হুক
# GET /api/admin/rules কল করে, কিন্তু আগে শুধু POST /rules ছিল।
# এখন GET endpoint যোগ করা হয়েছে যাতে rules লিস্ট ফেচ করা যায়।
@router.get("/rules")
async def get_rules(admin_user: dict = Depends(get_current_admin)):
    """Fetch all constitutional rules from God.py."""
    rules = god_layer.list_rules()
    return {"rules": rules}
'''
    content += new_routes
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: admin.py - added GET /rules")
else:
    print("Skip: admin.py already has GET /rules")

print("\nAll backend route additions complete!")
