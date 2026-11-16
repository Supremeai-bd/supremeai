import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_token, get_tenant_db
from core.monitoring.logging_config import logger
from core.tools.devops.gitlab_agent import GitLabAgent, get_user_gitlab_token
from database.session import get_db_session

router = APIRouter(prefix="/gitlab", tags=["gitlab"])


def _resolve_project(payload_project: str | None, db) -> str:
    target = (payload_project or "").strip()
    if not target:
        tenant_data = db.get_tenant_profile() if hasattr(db, "get_tenant_profile") else None
        target = ((tenant_data or {}).get("gitlab_project") or "").strip()
    if not target:
        raise HTTPException(
            status_code=400,
            detail="GitLab project not connected. Please provide project or connect in settings.",
        )
    return target


@asynccontextmanager
async def handle_gitlab_errors(operation_name: str, project: str | None = None):
    try:
        yield
    except HTTPException:
        raise
    except Exception as err:
        ref_code = uuid.uuid4().hex[:8]
        context = f" [project={project}]" if project else ""
        logger.error(f"GitLab {operation_name} failure (ref={ref_code}){context}: {err}")
        raise HTTPException(
            status_code=502, detail=f"GitLab operation failed (ref: {ref_code})"
        ) from err


async def _get_agent(user: dict, sql_db: AsyncSession, host: str = "https://gitlab.com") -> GitLabAgent:
    user_id = user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = await get_user_gitlab_token(user_id, sql_db)
    if not token:
        raise HTTPException(
            status_code=403, detail="GitLab integration not connected or token invalid."
        )
    return GitLabAgent(token=token, host=host)


class ConnectProjectRequest(BaseModel):
    project_path: str
    host: str = "https://gitlab.com"


class ImproveProjectRequest(BaseModel):
    project: str | None = None
    branch: str = "main"
    host: str = "https://gitlab.com"


class PushGitLabRequest(BaseModel):
    project: str | None = None
    branch: str = "main"
    commit_message: str = "AI: Automated improvements"
    file_contents: dict[str, str]
    host: str = "https://gitlab.com"
    create_mr: bool = True
    mr_title: str | None = None


class CreateMRRequest(BaseModel):
    project: str
    title: str
    description: str
    source_branch: str
    target_branch: str = "main"
    host: str = "https://gitlab.com"


@router.post("/connect")
async def connect_project(
    payload: ConnectProjectRequest,
    db=Depends(get_tenant_db),
    user=Depends(get_current_user_token),
    sql_db=Depends(get_db_session),
):
    async with handle_gitlab_errors("connect", payload.project_path):
        agent = await _get_agent(user, sql_db, host=payload.host)
        res = await agent.connect_project(payload.project_path)
        tenant_ref = db.tenant_root
        tenant_ref.set({"gitlab_project": payload.project_path}, merge=True)
        return {
            "status": "success",
            "message": f"Connected to GitLab project {payload.project_path}",
            "project": res,
        }


@router.post("/improve")
async def improve_project(
    payload: ImproveProjectRequest,
    db=Depends(get_tenant_db),
    user=Depends(get_current_user_token),
    sql_db=Depends(get_db_session),
):
    async with handle_gitlab_errors("improve", payload.project):
        project = _resolve_project(payload.project, db)
        agent = await _get_agent(user, sql_db, host=payload.host)
        analysis = await agent.analyze_project(project)
        return {"status": "success", "analysis": analysis}


@router.post("/push")
async def push_to_gitlab(
    payload: PushGitLabRequest,
    db=Depends(get_tenant_db),
    user=Depends(get_current_user_token),
    sql_db=Depends(get_db_session),
):
    async with handle_gitlab_errors("push", payload.project):
        if not payload.file_contents:
            raise HTTPException(
                status_code=400,
                detail="file_contents is required. Provide path -> content map.",
            )
        project = _resolve_project(payload.project, db)
        agent = await _get_agent(user, sql_db, host=payload.host)

        commit_res = await agent.commit_changes(
            project,
            payload.file_contents,
            payload.commit_message,
            payload.branch,
        )

        mr_url = None
        if payload.create_mr:
            mr_title = payload.mr_title or "SupremeAI: Automated Code Improvements"
            mr_desc = "AI analyzed the workspace and pushed improvements.\n\nApproval required before merging."
            mr_res = await agent.create_mr(
                project,
                mr_title,
                mr_desc,
                payload.branch,
                target_branch="main",
            )
            mr_url = mr_res.get("mr_url")

        return {
            "status": "success",
            "branch": commit_res["branch"],
            "commit_id": commit_res.get("commit_id"),
            "mr_url": mr_url,
            "message": "GitLab changes committed successfully.",
        }


@router.post("/mr")
async def create_merge_request(
    payload: CreateMRRequest,
    user=Depends(get_current_user_token),
    sql_db=Depends(get_db_session),
):
    async with handle_gitlab_errors("create_mr", payload.project):
        agent = await _get_agent(user, sql_db, host=payload.host)
        res = await agent.create_mr(
            payload.project,
            payload.title,
            payload.description,
            payload.source_branch,
            payload.target_branch,
        )
        return res


@router.get("/projects")
async def list_gitlab_projects(
    user=Depends(get_current_user_token),
    sql_db=Depends(get_db_session),
    host: str = "https://gitlab.com",
):
    async with handle_gitlab_errors("list_projects"):
        agent = await _get_agent(user, sql_db, host=host)
        projects = await agent.list_projects()
        return projects
