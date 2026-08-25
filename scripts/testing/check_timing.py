import os
import urllib.request
import json
import time

GH_TOKEN = "ghp_REDACTED"
RENDER_KEY = os.environ.get("RENDER_API_KEY", "")

# Fetch latest workflow run on main
gh_req = urllib.request.Request(
    "https://api.github.com/repos/SaifulHaqueNiloy/supremeai/actions/runs?branch=main&per_page=1",
    headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
)

try:
    with urllib.request.urlopen(gh_req) as response:
        gh_data = json.loads(response.read().decode())
        run = gh_data['workflow_runs'][0]
        print(f"[GITHUB] Workflow started at: {run['run_started_at']}")
        print(f"[GITHUB] Workflow status: {run['status']}")
except Exception as e:
    print(f"GH Error: {e}")

# Fetch latest render deploy
render_req = urllib.request.Request(
    "https://api.render.com/v1/services/srv-da666f8u01pc739bm3t0/deploys?limit=1",
    headers={"Authorization": f"Bearer {RENDER_KEY}", "Accept": "application/json"}
)

try:
    with urllib.request.urlopen(render_req) as response:
        render_data = json.loads(response.read().decode())
        if render_data:
            deploy = render_data[0]['deploy']
            print(f"[RENDER] Latest Deploy started at: {deploy['createdAt']}")
            print(f"[RENDER] Latest Deploy status: {deploy['status']}")
except Exception as e:
    print(f"Render Error: {e}")
