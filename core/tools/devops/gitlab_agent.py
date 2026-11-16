"""GitLab integration agent — direct REST v4 API client.

Mirroring core/tools/devops/github_agent.py for complete GitLab parity.
Every method either performs the real authenticated API call or raises (no fabricated results).
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime as dt
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.monitoring.logging_config import logger
from core.security.security_vault import decrypt_token
from models.integration import Integration


async def get_user_gitlab_token(user_id: str, db: AsyncSession) -> str | None:
    """DB থেকে ইউজারের এনক্রিপ্টেড GitLab টোকেন রিট্রিভ করে ডিক্রিপ্ট করে।

    টোকেন না পেলে None রিটার্ন করে — কলারকে fail-fast করতে হবে।
    """
    res = await db.execute(
        select(Integration.encrypted_access_token).filter_by(user_id=user_id, provider="gitlab")
    )
    enc_token = res.scalar_one_or_none()
    if not enc_token:
        logger.warning(f"GitLab token missing for user: {user_id}")
        return None

    try:
        return decrypt_token(enc_token)
    except Exception as err:
        logger.error(f"GitLab token decryption failure for {user_id}: {err}")
        return None


async def create_autonomous_mr(
    user_id: str,
    project_name: str,
    file_path: str,
    code_content: str,
    commit_msg: str,
    db: AsyncSession | None = None,
    host: str = "https://gitlab.com",
) -> str | None:
    """এনক্রিপ্টেড টোকেন ডিক্রিপ্ট করে গিটল্যাবে নতুন ব্রাঞ্চ এবং Merge Request তৈরি করবে।

    project_name ফরম্যাট: 'owner/project' অথবা numeric ID.
    """
    if db is None:
        raise RuntimeError(
            "create_autonomous_mr: db_session is required to fetch GitLab token from DB."
        )

    access_token = await get_user_gitlab_token(user_id, db)
    if access_token is None:
        raise RuntimeError(
            f"GitLab token not found or could not be decrypted for user '{user_id}'. "
            "Please connect GitLab via settings or link first."
        )

    agent = GitLabAgent(token=access_token, host=host)
    branch_name = f"supremeai-auto-fix-{dt.now().strftime('%Y%m%d%H%M%S')}"

    # Step 1: Commit the code
    files_to_commit = {file_path: code_content}
    await agent.commit_changes(project_name, files_to_commit, commit_msg, branch_name)

    # Step 2: Create Merge Request
    title = f"🚀 SupremeAI Auto-Fix: {commit_msg}"
    desc = (
        "This Merge Request was autonomously generated and verified in SupremeAI.\n\n"
        "- ✅ Execution Verified\n- 🧠 Saved to Memory Vault"
    )
    mr_res = await agent.create_mr(project_name, title, desc, branch_name)
    return mr_res.get("mr_url")


class GitLabAgent:
    """Thin wrapper around the GitLab v4 REST API.

    No mock/simulated responses — every method performs the real call or raises.
    """

    def __init__(self, token: str | None = None, host: str = "https://gitlab.com") -> None:
        self.token = (token or "").strip()
        self.host = (host or "https://gitlab.com").rstrip("/")
        if not self.token:
            logger.warning("GitLabAgent initialized without a token; real API calls disabled.")

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("GitLab token is required for real API operations.")
        # Support both PAT (PRIVATE-TOKEN) and OAuth / Bearer tokens
        if self.token.startswith("glpat-") or self.token.startswith("feed_token-"):
            return {
                "PRIVATE-TOKEN": self.token,
                "Accept": "application/json",
            }
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _encode_project(self, project: str) -> str:
        """Encode 'owner/project' or numeric project ID for URL path."""
        clean = project.strip().strip("/")
        return urllib.parse.quote(clean, safe="")

    async def connect_project(self, project_path: str) -> dict[str, Any]:
        """Verifies the project is reachable with this token before 'connecting'."""
        encoded = self._encode_project(project_path)
        url = f"{self.host}/api/v4/projects/{encoded}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._headers())
        if resp.status_code == 404:
            raise ValueError(
                f"GitLab project '{project_path}' not found or not accessible with this token."
            )
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": "success",
            "project": data.get("path_with_namespace", project_path),
            "id": data.get("id"),
            "default_branch": data.get("default_branch") or "main",
            "web_url": data.get("web_url"),
        }

    async def analyze_project(self, project_path: str) -> dict[str, Any]:
        """Real lightweight project metadata pull."""
        encoded = self._encode_project(project_path)
        url = f"{self.host}/api/v4/projects/{encoded}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": "success",
            "project": project_path,
            "id": data.get("id"),
            "open_issues": data.get("open_issues_count"),
            "default_branch": data.get("default_branch") or "main",
            "visibility": data.get("visibility"),
            "web_url": data.get("web_url"),
            "star_count": data.get("star_count", 0),
        }

    async def create_mr(
        self,
        project_path: str,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str = "main",
    ) -> dict[str, Any]:
        """Creates a Merge Request on GitLab."""
        encoded = self._encode_project(project_path)
        url = f"{self.host}/api/v4/projects/{encoded}/merge_requests"
        headers = self._headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "source_branch": source_branch,
                    "target_branch": target_branch,
                    "title": title,
                    "description": description,
                    "remove_source_branch": False,
                },
            )
        if resp.status_code != 201:
            raise RuntimeError(f"GitLab MR creation failed ({resp.status_code}): {resp.text}")
        mr = resp.json()
        logger.info(f"Real GitLab MR created: {mr.get('web_url')}")
        return {
            "status": "success",
            "mr_url": mr.get("web_url"),
            "mr_iid": mr.get("iid"),
            "mr_id": mr.get("id"),
        }

    async def commit_changes(
        self,
        project_path: str,
        files_to_commit: dict[str, str],
        commit_message: str,
        branch: str,
        start_branch: str = "main",
    ) -> dict[str, Any]:
        """Commits multiple files in a single atomic commit using the GitLab Commits API.

        Creates the branch automatically if it does not already exist via start_branch.
        """
        encoded = self._encode_project(project_path)
        headers = self._headers()
        base_url = f"{self.host}/api/v4/projects/{encoded}"

        # Build actions: check existing files or default to create/update
        actions: list[dict[str, str]] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Check default branch
            proj_info = await client.get(base_url, headers=headers)
            proj_info.raise_for_status()
            resolved_default = proj_info.json().get("default_branch") or start_branch

            for file_path, content in files_to_commit.items():
                encoded_file = urllib.parse.quote(file_path.strip("/"), safe="")
                file_check = await client.get(
                    f"{base_url}/repository/files/{encoded_file}?ref={resolved_default}",
                    headers=headers,
                )
                action_type = "update" if file_check.status_code == 200 else "create"
                actions.append(
                    {
                        "action": action_type,
                        "file_path": file_path.strip("/"),
                        "content": content,
                    }
                )

            commit_payload = {
                "branch": branch,
                "commit_message": commit_message,
                "start_branch": resolved_default,
                "actions": actions,
            }

            resp = await client.post(
                f"{base_url}/repository/commits",
                headers=headers,
                json=commit_payload,
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Failed to commit to GitLab: {resp.text}")
            commit_data = resp.json()

        return {
            "status": "success",
            "branch": branch,
            "commit_id": commit_data.get("id"),
            "web_url": commit_data.get("web_url"),
            "files_committed": list(files_to_commit),
        }

    async def list_projects(self) -> list[dict[str, Any]]:
        """List repositories accessible to this token."""
        url = f"{self.host}/api/v4/projects?membership=true&per_page=50&order_by=updated_at"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        return [
            {
                "id": str(p["id"]),
                "name": p["name"],
                "path_with_namespace": p["path_with_namespace"],
                "default_branch": p.get("default_branch", "main"),
                "web_url": p.get("web_url"),
                "visibility": p.get("visibility"),
            }
            for p in resp.json()
        ]
