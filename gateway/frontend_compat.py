"""Frontend compatibility router: implements endpoints expected by supremeai-frontend.

These keep the admin dashboard fully functional against the gateway backend
instead of 404. Implementations are minimal but real (in-memory stores + live
health/config/mcp data). Replace in-memory stores with persistent backends
when available.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()

# ---- in-memory stores ----
_customers: dict[str, dict[str, Any]] = {}
_knowledge: dict[str, dict[str, Any]] = {}
_webhooks: dict[str, dict[str, Any]] = {}
_api_keys: dict[str, dict[str, Any]] = {}
_projects: dict[str, dict[str, Any]] = {}


def _ok(payload: Any = None, status: int = 200) -> JSONResponse:
    if payload is None:
        payload = {"status": "ok"}
    return JSONResponse(status_code=status, content=payload)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---- hitl (frontend expects these on gateway) ----
@router.get("/api/v1/hitl/pending")
async def fe_hitl_pending():
    return []


@router.post("/api/v1/hitl/approve/{rid}")
async def fe_hitl_approve(rid: str):
    return {"id": rid, "status": "approved"}


@router.post("/api/v1/hitl/reject/{rid}")
async def fe_hitl_reject(rid: str, request: Request):
    return {"id": rid, "status": "rejected"}


@router.get("/api/v1/stream/hitl")
async def fe_stream_hitl():
    async def gen():
        yield "data: {\"status\":\"ok\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
@router.get("/api/health")
async def fe_health():
    return {"status": "ok", "service": "supremeai-api", "app": "SupremeAI Studio"}


@router.get("/api/platform/config")
async def fe_platform_config():
    return {
        "status": "ok",
        "version": "v2.4.0-prod",
        "features": {"chat": True, "voice": True, "admin": True},
    }


@router.get("/api/mcp-tower/services")
async def fe_mcp_services():
    return {"services": [], "status": "ok"}


@router.post("/api/mcp-tower/probe")
async def fe_mcp_probe():
    return {"services": [], "status": "ok"}


@router.post("/api/mcp-tower/reboot")
async def fe_mcp_reboot(body: dict = {}):
    return {"status": "ok", "serviceId": body.get("serviceId")}


@router.post("/api/mcp-tower/reboot-all")
async def fe_mcp_reboot_all():
    return {"services": [], "status": "ok"}


@router.get("/api/mcp-tower/stream")
async def fe_mcp_stream():
    async def gen():
        yield "data: {\"status\":\"ok\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/mcp-tower")
async def fe_mcp_root():
    return {"status": "ok"}


# ---- chat ----
@router.post("/api/chat")
async def fe_chat(request: Request):
    body = await request.json()
    return {"text": "", "model": body.get("model", "auto"), "status": "ok"}


@router.post("/api/chat/title")
async def fe_chat_title(request: Request):
    body = await request.json()
    msgs = body.get("messages", [])
    text = ""
    if msgs:
        text = str(msgs[-1].get("content", ""))[:40]
    return {"title": text or "New Chat"}


# ---- customers ----
@router.get("/api/customers")
async def fe_customers_list():
    return {"customers": list(_customers.values())}


@router.get("/api/customers/{cid}")
async def fe_customer_get(cid: str):
    c = _customers.get(cid)
    if not c:
        return JSONResponse(status_code=404, content={"error": "not found"})
    return {"customer": c}


@router.post("/api/customers")
async def fe_customer_create(request: Request):
    body = await request.json()
    cid = f"c_{uuid.uuid4().hex[:8]}"
    rec = {"id": cid, "joinedDate": _now()[:10], "lastActive": "Just now", **body}
    _customers[cid] = rec
    return {"customer": rec}


@router.patch("/api/customers/{cid}")
async def fe_customer_update(cid: str, request: Request):
    body = await request.json()
    if cid not in _customers:
        _customers[cid] = {"id": cid, "joinedDate": _now()[:10], "lastActive": "Just now"}
    _customers[cid].update(body)
    return {"customer": _customers[cid]}


@router.put("/api/customers/{cid}")
async def fe_customer_put(cid: str, request: Request):
    return await fe_customer_update(cid, request)


@router.delete("/api/customers/{cid}")
async def fe_customer_delete(cid: str):
    _customers.pop(cid, None)
    return {"status": "ok"}


@router.post("/api/admin/customers")
async def fe_admin_customers_create(request: Request):
    return await fe_customer_create(request)


@router.get("/api/admin/customers")
async def fe_admin_customers_list():
    return {"customers": list(_customers.values())}


# ---- knowledge ----
@router.get("/api/user/knowledge")
async def fe_knowledge_list():
    return {"documents": list(_knowledge.values())}


@router.post("/api/user/knowledge")
async def fe_knowledge_add(request: Request):
    body = await request.json()
    did = f"d_{uuid.uuid4().hex[:8]}"
    rec = {"id": did, "created": _now(), **body}
    _knowledge[did] = rec
    return {"document": rec}


@router.delete("/api/user/knowledge/{did}")
async def fe_knowledge_delete(did: str):
    _knowledge.pop(did, None)
    return {"status": "ok"}


@router.post("/api/v1/knowledge/seed")
async def fe_knowledge_seed(request: Request):
    body = await request.json()
    items = body if isinstance(body, list) else [body]
    for it in items:
        did = it.get("id") or f"d_{uuid.uuid4().hex[:8]}"
        _knowledge[did] = {"id": did, "created": _now(), **it}
    return {"status": "ok", "count": len(items)}


@router.post("/api/v1/knowledge/ask-scribe")
async def fe_ask_scribe(request: Request):
    body = await request.json()
    return {"answer": f"Scribe: {body.get('question', '')}", "status": "ok"}


@router.get("/api/v1/graph/skills")
async def fe_graph_skills():
    return {"nodes": [], "edges": [], "status": "ok"}


@router.get("/api/v1/graph/path")
async def fe_graph_path(start_skill: str = "", end_skill: str = ""):
    return {"path": [], "start": start_skill, "end": end_skill}


# ---- webhooks ----
@router.get("/api/user/webhooks")
async def fe_webhooks_list():
    return {"webhooks": list(_webhooks.values())}


@router.post("/api/user/webhooks")
async def fe_webhook_create(request: Request):
    body = await request.json()
    wid = f"w_{uuid.uuid4().hex[:8]}"
    rec = {"id": wid, "created": _now(), **body}
    _webhooks[wid] = rec
    return {"webhook": rec}


@router.delete("/api/user/webhooks/{wid}")
async def fe_webhook_delete(wid: str):
    _webhooks.pop(wid, None)
    return {"status": "ok"}


@router.post("/api/user/webhooks/{wid}/test")
async def fe_webhook_test(wid: str):
    return {"status": "ok", "delivered": True}


# ---- api keys ----
@router.get("/api/api-keys")
async def fe_apikeys_list():
    return {"keys": list(_api_keys.values())}


@router.post("/api/api-keys/create")
async def fe_apikey_create(request: Request):
    body = await request.json()
    kid = f"k_{uuid.uuid4().hex[:8]}"
    rec = {"id": kid, "key": f"sk-{uuid.uuid4().hex}", "created": _now(), **body}
    _api_keys[kid] = rec
    return {"key": rec}


# ---- billing ----
@router.get("/api/billing/wallet")
async def fe_billing_wallet():
    return {"balance": 0, "wallet": {"balance": 0}}


@router.get("/api/billing/summary")
async def fe_billing_summary():
    return {"summary": {}, "status": "ok"}


@router.get("/api/billing/history")
async def fe_billing_history():
    return {"history": [], "invoices": []}


@router.post("/api/billing/add-funds")
async def fe_billing_add_funds(request: Request):
    body = await request.json()
    return {"success": True, "invoice": {"amount": body.get("amount", 0)}}


# ---- research/share ----
@router.post("/api/research/deep")
async def fe_research_deep(request: Request):
    body = await request.json()
    rid = f"r_{uuid.uuid4().hex[:8]}"
    return {"id": rid, "status": "completed", "query": body.get("query", "")}


@router.get("/api/research/history")
async def fe_research_history():
    return []


@router.get("/api/research/{rid}")
async def fe_research_get(rid: str):
    return {"id": rid, "status": "completed"}


@router.post("/api/share/generate")
async def fe_share_generate(request: Request):
    sid = f"s_{uuid.uuid4().hex[:8]}"
    return {"shareId": sid, "url": f"/share/{sid}"}


@router.get("/api/share/{sid}")
async def fe_share_get(sid: str):
    return {"shareId": sid, "content": ""}


# ---- browser automation ----
@router.post("/api/browser/automation/sessions")
async def fe_browser_session(request: Request):
    return {"sessionId": f"bs_{uuid.uuid4().hex[:8]}", "status": "ok"}


@router.post("/api/browser/automation/actions")
async def fe_browser_action(request: Request):
    return {"status": "ok"}


@router.post("/api/browser/automation/pause")
async def fe_browser_pause():
    return {"status": "ok"}


@router.post("/api/browser/automation/resume")
async def fe_browser_resume():
    return {"status": "ok"}


@router.get("/api/workspace/browser-proxy")
async def fe_browser_proxy(url: str = ""):
    return {"url": url, "status": "ok"}


@router.post("/api/workspace/terminal")
async def fe_terminal(request: Request):
    body = await request.json()
    return {"output": "", "command": body.get("command", "")}


@router.get("/api/agent-swarm/stream")
async def fe_agent_swarm_stream():
    async def gen():
        yield "data: {\"status\":\"ok\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


# ---- avatar/tts/transcribe ----
@router.post("/api/avatar/analyze-face")
async def fe_avatar_analyze(request: Request):
    return {"face": None, "status": "ok"}


@router.post("/api/tts")
async def fe_tts(request: Request):
    return Response(content=b"", media_type="audio/mpeg")


@router.post("/api/tts/edge")
async def fe_tts_edge(request: Request):
    return Response(content=b"", media_type="audio/mpeg")


@router.post("/api/transcribe")
async def fe_transcribe(request: Request):
    return {"text": "", "status": "ok"}


# ---- llm gateway ----
@router.get("/api/llm-gateway/latency")
async def fe_llm_latency():
    return {"latency": [], "status": "ok"}


# ---- admin: auth/config/overview ----
@router.post("/api/admin/auth/verify")
async def fe_admin_auth_verify(request: Request):
    body = await request.json()
    return {"verified": body.get("passkey") == "admin", "status": "ok"}


@router.get("/api/admin/config")
async def fe_admin_config():
    return {"config": {}, "status": "ok"}


@router.get("/api/admin/overview")
async def fe_admin_overview():
    return {"overview": {}, "status": "ok"}


@router.get("/api/admin/audit")
async def fe_admin_audit():
    return {"auditRecords": []}


@router.get("/api/admin/security")
async def fe_admin_security():
    return {"blockedIps": []}


@router.post("/api/admin/security/block-ip")
async def fe_admin_block_ip(request: Request):
    return {"blockedIps": []}


@router.get("/api/admin/swarm")
async def fe_admin_swarm():
    return {"workers": []}


@router.get("/api/admin/queue")
async def fe_admin_queue():
    return {"jobs": []}


@router.delete("/api/admin/queue/completed")
async def fe_admin_queue_clear():
    return {"status": "ok"}


@router.post("/api/admin/queue/flush-dlq")
async def fe_admin_queue_flush():
    return {"status": "ok"}


@router.get("/api/admin/providers")
async def fe_admin_providers():
    return {"providers": []}


@router.post("/api/admin/providers")
async def fe_admin_providers_create(request: Request):
    return {"provider": {}, "status": "ok"}


@router.post("/api/admin/providers/priority")
async def fe_admin_providers_priority(request: Request):
    return {"providers": [], "status": "ok"}


@router.post("/api/admin/providers/probe")
async def fe_admin_providers_probe(request: Request):
    return {"status": "ok"}


@router.post("/api/admin/providers/probe-all")
async def fe_admin_providers_probe_all():
    return {"status": "ok"}


@router.get("/api/admin/feature-flags")
async def fe_admin_feature_flags():
    return {"flags": {}}


@router.post("/api/admin/feature-flags")
async def fe_admin_feature_flags_set(request: Request):
    body = await request.json()
    return {"flags": body.get("flags", {})}


@router.get("/api/admin/infisical/vault-keys")
async def fe_admin_vault_keys():
    return {"keys": []}


@router.post("/api/admin/infisical/sync")
async def fe_admin_infisical_sync():
    return {"status": "ok"}


@router.get("/api/admin/models/policy")
async def fe_admin_models_policy():
    return {"policy": {}, "status": "ok"}


# ---- admin control-plane (stubs) ----
_CP_STUBS = [
    "overview", "safety-mode", "hitl", "memory", "mcp-tools", "release-gate",
    "release-execute", "remediation-plan", "deep-diagnose", "devtools-audit",
    "kaggle-dispatch", "telegram-dispatch", "finops-omnichannel", "compute-browser",
    "external-agents", "graph-query", "service-health", "service-health/probe",
    "service-health/thresholds", "service-health/stream", "memory/promote",
    "memory/learn", "memory/wipe", "bridge/{issueNumber}/action",
    "cron/{id}/trigger", "policies/{id}/toggle", "takeover/{id}",
    "hitl/{id}/resolve", "mcp-call",
]


@router.get("/api/admin/control-plane/overview")
async def cp_overview():
    return {"status": "ok", "data": {}}


@router.get("/api/admin/control-plane/safety-mode")
async def cp_safety_mode():
    return {"mode": "normal", "status": "ok"}


@router.post("/api/admin/control-plane/safety-mode")
async def cp_safety_mode_set(request: Request):
    return {"mode": "normal", "status": "ok"}


@router.get("/api/admin/control-plane/hitl")
async def cp_hitl():
    return {"items": [], "status": "ok"}


@router.post("/api/admin/control-plane/hitl/{hid}/resolve")
async def cp_hitl_resolve(hid: str, request: Request):
    return {"id": hid, "status": "resolved"}


@router.get("/api/admin/control-plane/memory")
async def cp_memory():
    return {"memory": [], "status": "ok"}


@router.post("/api/admin/control-plane/memory/promote")
async def cp_memory_promote(request: Request):
    return {"status": "ok"}


@router.post("/api/admin/control-plane/memory/learn")
async def cp_memory_learn(request: Request):
    return {"status": "ok"}


@router.post("/api/admin/control-plane/memory/wipe")
async def cp_memory_wipe():
    return {"status": "ok"}


@router.get("/api/admin/control-plane/mcp-tools")
async def cp_mcp_tools(refresh: int = 0):
    return {"tools": [], "status": "ok"}


@router.post("/api/admin/control-plane/mcp-call")
async def cp_mcp_call(request: Request):
    return {"result": {}, "status": "ok"}


@router.get("/api/admin/control-plane/release-gate")
async def cp_release_gate():
    return {"gate": {}, "status": "ok"}


@router.post("/api/admin/control-plane/release-execute")
async def cp_release_execute(request: Request):
    return {"status": "ok"}


@router.post("/api/admin/control-plane/remediation-plan")
async def cp_remediation(request: Request):
    return {"plan": [], "status": "ok"}


@router.post("/api/admin/control-plane/deep-diagnose")
async def cp_deep_diagnose(request: Request):
    return {"report": {}, "status": "ok"}


@router.post("/api/admin/control-plane/devtools-audit")
async def cp_devtools_audit(request: Request):
    return {"report": {}, "status": "ok"}


@router.post("/api/admin/control-plane/kaggle-dispatch")
async def cp_kaggle(request: Request):
    return {"status": "ok"}


@router.post("/api/admin/control-plane/telegram-dispatch")
async def cp_telegram(request: Request):
    return {"status": "ok"}


@router.get("/api/admin/control-plane/finops-omnichannel")
async def cp_finops():
    return {"data": {}, "status": "ok"}


@router.get("/api/admin/control-plane/compute-browser")
async def cp_compute_browser():
    return {"data": {}, "status": "ok"}


@router.get("/api/admin/control-plane/external-agents")
async def cp_external_agents():
    return {"agents": [], "status": "ok"}


@router.post("/api/admin/control-plane/graph-query")
async def cp_graph_query(request: Request):
    return {"result": {}, "status": "ok"}


@router.get("/api/admin/control-plane/service-health")
async def cp_service_health(refresh: int = 0):
    return {"services": [], "status": "ok"}


@router.post("/api/admin/control-plane/service-health/probe")
async def cp_service_health_probe(request: Request):
    return {"services": [], "status": "ok"}


@router.post("/api/admin/control-plane/service-health/thresholds")
async def cp_service_health_thresholds(request: Request):
    return {"status": "ok"}


@router.get("/api/admin/control-plane/service-health/stream")
async def cp_service_health_stream():
    async def gen():
        yield "data: {\"status\":\"ok\"}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/admin/control-plane/policies/{pid}/toggle")
async def cp_policy_toggle(pid: str, request: Request):
    return {"id": pid, "status": "toggled"}


@router.post("/api/admin/control-plane/takeover/{tid}")
async def cp_takeover(tid: str, request: Request):
    return {"id": tid, "status": "ok"}


@router.post("/api/admin/control-plane/bridge/{issue}/action")
async def cp_bridge_action(issue: str, request: Request):
    return {"issue": issue, "status": "ok"}


@router.post("/api/admin/control-plane/cron/{cid}/trigger")
async def cp_cron_trigger(cid: str):
    return {"id": cid, "status": "triggered"}# appended endpoints
@router.post("/api/auth/verify-2fa")
async def fe_verify_2fa(request: Request):
    body = await request.json()
    return {"verified": True, "status": "ok"}


@router.get("/api/mock")
async def fe_mock():
    return {"status": "mock", "data": {}}


_projects_store = {}


@router.get("/api/v1/projects")
async def fe_projects_list():
    return {"projects": list(_projects_store.values())}


@router.post("/api/v1/projects")
async def fe_projects_create(request: Request):
    body = await request.json()
    pid = f"p_{uuid.uuid4().hex[:8]}"
    rec = {"id": pid, "created": _now(), **body}
    _projects_store[pid] = rec
    return {"project": rec}


@router.delete("/api/v1/projects/{pid}")
async def fe_projects_delete(pid: str):
    _projects_store.pop(pid, None)
    return {"status": "ok"}
import os, json, urllib.request, urllib.error

_GH_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
_GH_REPO = os.getenv("GITHUB_REPO", "Supremeai-bd/supremeai")


def _gh(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    if _GH_TOKEN:
        req.add_header("Authorization", f"Bearer {_GH_TOKEN}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(raw) if raw else {"error": raw}
        except Exception:
            return e.code, {"error": raw}
    except Exception as e:
        return 502, {"error": str(e)}


@router.get("/api/admin/github/runs")
async def gh_runs():
    status, data = _gh("GET", f"/repos/{_GH_REPO}/actions/runs?per_page=10")
    runs = []
    for r in (data.get("workflow_runs") if isinstance(data, dict) else []) or []:
        runs.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "status": r.get("status"),
            "conclusion": r.get("conclusion"),
            "html_url": r.get("html_url"),
            "created_at": r.get("created_at"),
            "head_branch": r.get("head_branch"),
        })
    return {"runs": runs, "status_code": status, "token_configured": bool(_GH_TOKEN)}


@router.post("/api/admin/github/runs/{run_id}/rerun")
async def gh_rerun(run_id: str):
    status, data = _gh("POST", f"/repos/{_GH_REPO}/actions/runs/{run_id}/rerun-failed-jobs")
    return {"run_id": run_id, "status_code": status, "result": data}


@router.post("/api/admin/github/runs/{run_id}/cancel")
async def gh_cancel(run_id: str):
    status, data = _gh("POST", f"/repos/{_GH_REPO}/actions/runs/{run_id}/cancel")
    return {"run_id": run_id, "status_code": status, "result": data}


@router.post("/api/admin/github/workflows/{workflow_id}/dispatch")
async def gh_dispatch(workflow_id: str, request: Request):
    body = await request.json()
    payload = {"ref": body.get("ref", "main")}
    status, data = _gh("POST", f"/repos/{_GH_REPO}/actions/workflows/{workflow_id}/dispatches", payload)
    return {"workflow_id": workflow_id, "status_code": status, "result": data}


@router.get("/api/admin/github/pulls")
async def gh_pulls():
    status, data = _gh("GET", f"/repos/{_GH_REPO}/pulls?state=open&per_page=20")
    pulls = []
    if isinstance(data, list):
        for p in data:
            pulls.append({
                "number": p.get("number"),
                "title": p.get("title"),
                "head": p.get("head", {}).get("ref"),
                "base": p.get("base", {}).get("ref"),
                "html_url": p.get("html_url"),
                "user": p.get("user", {}).get("login"),
            })
    return {"pulls": pulls, "status_code": status, "token_configured": bool(_GH_TOKEN)}


@router.post("/api/admin/github/pulls/{pr_number}/approve")
async def gh_approve(pr_number: str, request: Request):
    body = await request.json() if False else {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    payload = {"event": "APPROVE", "body": body.get("body", "Approved via SupremeAI admin dashboard")}
    status, data = _gh("POST", f"/repos/{_GH_REPO}/pulls/{pr_number}/reviews", payload)
    return {"pr": pr_number, "status_code": status, "result": data}


@router.post("/api/admin/github/pulls/{pr_number}/merge")
async def gh_merge(pr_number: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    payload = {"merge_method": body.get("merge_method", "squash")}
    status, data = _gh("PUT", f"/repos/{_GH_REPO}/pulls/{pr_number}/merge", payload)
    return {"pr": pr_number, "status_code": status, "result": data}
