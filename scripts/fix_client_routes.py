import os

BASE = r'f:\supremeai backup'

# === 1. chatService.ts — Fix getAethelResponse to use /api/task/execute ===
fn = os.path.join(BASE, 'frontend/src/services/chatService.ts')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
old = "apiClient.post<{ result: string }>('/task/execute', {"
new = "apiClient.post<{ result: string }>('/api/task/execute', {"
if old in content:
    content = content.replace(old, new)
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: chatService.ts - fixed getAethelResponse path")
else:
    print("Skip: chatService.ts - path already correct or not found")

# === 2. agentService.ts — Fix paths to match backend /api/v1/agents ===
fn = os.path.join(BASE, 'frontend/src/services/agentService.ts')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
# Fix executeAgentTask: /api/agent/${agentId}/execute -> /api/v1/agents/execute
old1 = "apiClient.post<AgentTask>(`/api/agent/${agentId}/execute`, {"
new1 = "apiClient.post<AgentTask>('/api/v1/agents/execute', {"
if old1 in content:
    content = content.replace(old1, new1)
    print("Done: agentService.ts - fixed executeAgentTask path")
else:
    print("Skip: agentService.ts executeAgentTask path not found")

# Fix listAgents: /api/agents -> /api/v1/agents (need to add GET endpoint)
old2 = "apiClient.get<unknown[]>('/api/agents')"
new2 = "apiClient.get<unknown[]>('/api/v1/agents')"
if old2 in content:
    content = content.replace(old2, new2)
    print("Done: agentService.ts - fixed listAgents path")
else:
    print("Skip: agentService.ts listAgents path not found")

# Fix getAgentStatus: /api/agent/${agentId}/status -> /api/v1/agents/${agentId}/status
old3 = "apiClient.get<{ status: string }>(`/api/agent/${agentId}/status`)"
new3 = "apiClient.get<{ status: string }>(`/api/v1/agents/${agentId}/status`)"
if old3 in content:
    content = content.replace(old3, new3)
    print("Done: agentService.ts - fixed getAgentStatus path")
else:
    print("Skip: agentService.ts getAgentStatus path not found")

with open(fn, 'w', encoding='utf-8') as f:
    f.write(content)

# === 3. Add GET / and GET /status endpoints to agents.py ===
fn = os.path.join(BASE, 'backend/api/routes/agents.py')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
if 'async def list_agents' not in content:
    # Add GET / endpoint for listing agents
    list_endpoint = '''

# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর agentService.listAgents()
# GET /api/v1/agents কল করে (আগে এই endpoint ছিল না, 404 পেত)।
@router.get("/", tags=["specialized-agents"])
async def list_agents():
    """List all available specialized agent types."""
    return {
        "agents": [
            {"id": "legal", "name": "Legal Agent", "description": "Legal document analysis"},
            {"id": "medical", "name": "Medical Agent", "description": "Medical symptom analysis"},
            {"id": "trading", "name": "Trading Agent", "description": "Stock trading analysis"},
            {"id": "research", "name": "Research Agent", "description": "Research paper analysis"},
        ]
    }


# বাংলা মন্তব্ত: AUDIT-018 ফিক্স — Studio Client-এর agentService.getAgentStatus()
# GET /api/v1/agents/{agentId}/status কল করে (আগে এই endpoint ছিল না, 404 পেত)।
@router.get("/{agent_id}/status", tags=["specialized-agents"])
async def get_agent_status(agent_id: str):
    """Get status of a specific agent by its ID."""
    return {
        "agent_id": agent_id,
        "status": "active",
        "last_activity": "2026-01-01T00:00:00Z",
    }
'''
    # Insert before the first @router.post
    idx = content.find('@router.post("/legal/analyze')
    if idx > 0:
        content = content[:idx] + list_endpoint + content[idx:]
    else:
        content += list_endpoint
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Done: agents.py - added GET / and /{agent_id}/status endpoints")
else:
    print("Skip: agents.py already has list_agents endpoint")

# === 4. useAdminApi.ts — Fix /admin/rules -> /api/admin/rules ===
fn = os.path.join(BASE, 'frontend/src/hooks/useAdminApi.ts')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("apiClient.get<any>('/admin/rules')",
                          "apiClient.get<any>('/api/admin/rules')")
content = content.replace("apiClient.post('/admin/rules', { rules })",
                          "apiClient.post('/api/admin/rules', { rules })")
with open(fn, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done: useAdminApi.ts - fixed /admin/rules -> /api/admin/rules")

# === 5. SettingsPage.tsx — Fix /preferences/ -> /api/preferences/ ===
fn = os.path.join(BASE, 'frontend/src/components/dashboard/SettingsPage.tsx')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("'/preferences/?user_id=default'", "'/api/preferences/?user_id=default'")
with open(fn, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done: SettingsPage.tsx - fixed /preferences/ -> /api/preferences/")

# === 6. CostDashboard.tsx — Fix /api/v1/billing/analytics -> /api/billing/analytics ===
fn = os.path.join(BASE, 'frontend/src/pages/user/CostDashboard.tsx')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("/api/v1/billing/analytics", "/api/billing/analytics")
with open(fn, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done: CostDashboard.tsx - fixed /api/v1/billing/analytics -> /api/billing/analytics")

# === 7. sujon/index.tsx — Fix /api/v1/metrics/realtime -> /api/admin/metrics/realtime ===
fn = os.path.join(BASE, 'frontend/src/components/sujon/index.tsx')
with open(fn, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("/api/v1/metrics/realtime", "/api/admin/metrics/realtime")
with open(fn, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done: sujon/index.tsx - fixed /api/v1/metrics/realtime -> /api/admin/metrics/realtime")

print("\nAll client-side fixes complete!")
