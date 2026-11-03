"""Unit tests for MultiPlatformOrchestrator (Genkit/Claude/ChatGPT to Real Code & Codespaces)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.routes.web_ai_proxy import router
from core.multi_platform_orchestrator import (
    ActionType,
    MultiPlatformOrchestrator,
    default_orchestrator,
)


def test_parse_claude_or_chatgpt_with_explicit_filepath():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    Claude বা ChatGPT-এর মতো আউটপুট যেখানে হেডার বা ব্লকে ফাইলের নাম স্পষ্ট থাকে।
    """
    raw_ai_text = """
Here is the optimized authentication middleware:

### backend/core/auth_middleware.py
```python
import time

class AuthMiddleware:
    def __init__(self):
        self.started_at = time.time()
```

You can verify this change by running:
```bash
pytest backend/tests/test_auth.py
```
"""
    orchestrator = MultiPlatformOrchestrator()
    plan = orchestrator.parse_ai_output(
        raw_output=raw_ai_text,
        repo_name="SaifulHaqueNiloy/supremeai",
        branch="feat/web-ai-session-bridge",
        source_platform="claude",
    )

    assert plan.source_platform == "claude"
    assert len(plan.file_actions) == 1
    action = plan.file_actions[0]
    assert action.file_path == "backend/core/auth_middleware.py"
    assert "class AuthMiddleware:" in action.content
    assert action.action_type == ActionType.MODIFY

    assert "pytest backend/tests/test_auth.py" in plan.verification_commands
    assert "codespaces/new?repo=SaifulHaqueNiloy/supremeai" in plan.codespaces_url
    assert "gitpod.io/#https://github.com/SaifulHaqueNiloy/supremeai" in plan.gitpod_url


def test_parse_generic_code_block_infers_natural_filename():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    ফাইলপাথ উল্লেখ না থাকলেও ভেতরের ক্লাস/কনটেন্ট দেখে অর্গানিক ফাইলের নাম অনুমান করা।
    """
    raw_code = """
Here is the user profile card implementation:

```tsx
import React from 'react';

export function UserProfileCard() {
    return <div>User Profile</div>;
}
```
"""
    orchestrator = MultiPlatformOrchestrator()
    plan = orchestrator.parse_ai_output(raw_code, source_platform="chatgpt")

    assert len(plan.file_actions) == 1
    action = plan.file_actions[0]
    assert action.file_path == "UserProfileCard.tsx"
    assert "export function UserProfileCard" in action.content


def test_apply_plan_locally_and_path_traversal_guard():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    পাথ ট্রাভার্সাল (../../etc/passwd) ঠেকানো এবং সঠিক ফাইলে কোড প্রয়োগ যাচাই।
    """
    orchestrator = MultiPlatformOrchestrator()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        malicious_plan = orchestrator.parse_ai_output("""
### ../../outside_root.py
```python
x = 1
```
### src/safe_module.py
```python
y = 2
```
""")
        res = orchestrator.apply_plan_locally(malicious_plan, workspace_root=tmp_path)

        assert "src/safe_module.py" in res.applied_files
        assert (tmp_path / "src" / "safe_module.py").read_text() == "y = 2"
        # ক্ষতিকর পাথ ব্লক হয়েছে
        assert any("Security: Path traversal attempt blocked" in err for err in res.errors)


def test_orchestrator_api_endpoint():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    FastAPI এন্ডপয়েন্ট /v1/orchestrator/parse-and-plan ঠিকমতো রেসপন্স দিচ্ছে কিনা যাচাই।
    """
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    payload = {
        "raw_ai_output": "### config/app.py\n```python\nDEBUG = True\n```",
        "repo_name": "SaifulHaqueNiloy/supremeai",
        "branch": "main",
        "source_platform": "genkit",
    }
    response = client.post("/v1/orchestrator/parse-and-plan", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["source_platform"] == "genkit"
    assert data["engine_brand"] == "SupremeAI Autonomous Core"
    assert "Supreme Solution:" in data["platform_agnostic_summary"]
    assert data["supreme_workspace_url"] is not None
    assert len(data["file_actions"]) == 1
    assert data["file_actions"][0]["file_path"] == "config/app.py"
    assert "codespaces/new" in data["codespaces_url"]
    assert "gitpod.io" in data["gitpod_url"]
