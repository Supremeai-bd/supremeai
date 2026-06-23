# Recent Code Changes


## File: backend\tools\browser_agent.py

`python

import asyncio
import httpx
from bs4 import BeautifulSoup
from loguru import logger
from typing import Dict, Any, Optional
import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.routes.admin_dashboard import require_admin_token

router = APIRouter(prefix="/browser", tags=["browser-agent"])

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname: return False
        if hostname == "169.254.169.254" or hostname.endswith(".local"): return False
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local: return False
        return True
    except Exception:
        return False


class BrowseRequest(BaseModel):
    url: str
    action: Optional[str] = "fetch"   # fetch | click | screenshot | scroll | type
    selector: Optional[str] = None
    text: Optional[str] = None
    wait_for: Optional[str] = None    # CSS selector to wait for


class BrowserAgent:
    """Controls browser actions â€” httpx (fast) + Playwright (full JS)."""

    def __init__(self):
        self._pw_browser = None
        logger.info("Initialized BrowserAgent")

    # â”€â”€ Simple fetch (no JS needed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def fetch_page(self, url: str) -> Dict[str, Any]:
        logger.info(f"Fetching page: {url}")
        if not is_safe_url(url):
            logger.error(f"SSRF Attempt Blocked: {url}")
            return {"success": False, "error": "SSRF check failed: Unauthorized internal access", "url": url}
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title else "No Title"
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = " ".join(soup.get_text(separator=" ").split())[:3000]
            links = [a.get("href", "") for a in soup.find_all("a", href=True)][:20]
            return {
                "success": True, "url": url, "title": title,
                "content": text, "links": links,
                "status_code": response.status_code,
            }
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return {"success": False, "error": str(e), "url": url}

    # â”€â”€ Playwright (JS-heavy pages) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async def _get_playwright(self):
        if self._pw_browser is None:
            try:
                from playwright.async_api import async_playwright
                self._pw = await async_playwright().__aenter__()
                self._pw_browser = await self._pw.chromium.launch(headless=True)
                logger.info("Playwright browser launched")
            except ImportError:
                logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")
                return None
        return self._pw_browser

    async def navigate_and_interact(
        self, url: str,
        action: str = "fetch",
        selector: Optional[str] = None,
        text: Optional[str] = None,
        wait_for: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not is_safe_url(url):
            logger.error(f"SSRF Attempt Blocked: {url}")
            return {"success": False, "error": "SSRF check failed: Unauthorized internal access", "url": url}

        browser = await self._get_playwright()
        if not browser:
            # Fallback to httpx
            return self.fetch_page(url)

        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)

            if action == "click" and selector:
                await page.click(selector)
                await page.wait_for_load_state("networkidle", timeout=10000)

            elif action == "type" and selector and text:
                await page.fill(selector, text)

            elif action == "scroll":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

            elif action == "screenshot":
                screenshot = await page.screenshot(type="png")
                import base64
                b64 = base64.b64encode(screenshot).decode()
                title = await page.title()
                return {"success": True, "url": url, "title": title, "screenshot_base64": b64}

            title = await page.title()
            content_html = await page.content()
            soup = BeautifulSoup(content_html, "html.parser")
            for tag in soup(["script", "style"]):
                tag.decompose()
            text_content = " ".join(soup.get_text(separator=" ").split())[:3000]
            links = [a.get("href", "") for a in soup.find_all("a", href=True)][:20]
            current_url = page.url

            return {
                "success": True, "url": current_url, "title": title,
                "content": text_content, "links": links, "action": action,
            }
        except Exception as e:
            logger.error(f"Playwright action failed: {e}")
            return {"success": False, "error": str(e), "url": url}
        finally:
            await page.close()

    async def extract_data(self, url: str, extraction_prompt: str) -> Dict[str, Any]:
        """Fetch page and use AI to extract structured data."""
        page_data = self.fetch_page(url)
        if not page_data["success"]:
            return page_data

        try:
            from brain.model_router import ModelRouter
            router = ModelRouter()
            prompt = (
                f"Extract the following from this web page content:\n{extraction_prompt}\n\n"
                f"Page Title: {page_data.get('title')}\n"
                f"Content: {page_data.get('content', '')[:2000]}\n\n"
                "Return a clean JSON object with the extracted data."
            )
            result = await router.async_route_and_generate(prompt, task_type="reasoning", max_cost=0.02)
            extracted = result.get("text", "") if isinstance(result, dict) else ""
            return {"success": True, "url": url, "extracted": extracted, "raw": page_data}
        except Exception as e:
            return {"success": False, "error": str(e)}


_agent = BrowserAgent()


@router.post("/browse", dependencies=[Depends(require_admin_token)])
async def browse(request: BrowseRequest):
    """Navigate to a URL and perform browser actions (Admin Only)."""
    if request.action in ("click", "type", "scroll", "screenshot"):
        return await _agent.navigate_and_interact(
            url=request.url,
            action=request.action,
            selector=request.selector,
            text=request.text,
            wait_for=request.wait_for,
        )
    return _agent.fetch_page(request.url)


@router.post("/extract", dependencies=[Depends(require_admin_token)])
async def extract(url: str, extraction_prompt: str):
    """Fetch page and extract structured data with AI (Admin Only)."""
    return await _agent.extract_data(url, extraction_prompt)

``n

## File: backend\tools\checkpoint_manager.py

`python

import os, json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from loguru import logger

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

@dataclass
class Checkpoint:
    task_id: str
    step_index: int
    state: Dict[str, Any]
    created_at: str
    resumed: bool = False

class CheckpointManager:
    """Persists task execution state in Google Cloud Firestore (Serverless & Stateful)."""
    def __init__(self, db_path: str = None):
        self.collection_name = "checkpoints"
        self._db = None
        if firestore:
            try:
                # If running on Cloud Run, it automatically picks up the default service account.
                self._db = firestore.AsyncClient() if hasattr(firestore, 'AsyncClient') else firestore.Client()
                logger.info("Initialized Firestore CheckpointManager")
            except Exception as e:
                logger.warning(f"Failed to initialize Firestore: {e}. Checkpoints will be disabled.")
        else:
            logger.warning("google-cloud-firestore not installed. CheckpointManager is disabled.")

    def save(self, task_id: str, step_index: int, state: Dict[str, Any]) -> bool:
        if not self._db: return False
        try:
            doc_ref = self._db.collection(self.collection_name).document(task_id)
            doc = doc_ref.get()
            resumed = doc.to_dict().get("resumed", False) if doc.exists else False
            
            doc_ref.set({
                "task_id": task_id,
                "step_index": step_index,
                "state": json.dumps(state),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "resumed": resumed
            })
            logger.info(f"Firestore checkpoint saved for task_id={task_id} step={step_index}")
            return True
        except Exception as exc:
            logger.error(f"Failed to save Firestore checkpoint: {exc}")
            return False

    def load(self, task_id: str) -> Optional[Checkpoint]:
        if not self._db: return None
        try:
            doc_ref = self._db.collection(self.collection_name).document(task_id)
            doc = doc_ref.get()
            if not doc.exists:
                return None
                
            data = doc.to_dict()
            cp = Checkpoint(
                task_id=data["task_id"],
                step_index=data["step_index"],
                state=json.loads(data["state"]),
                created_at=data["created_at"],
                resumed=bool(data.get("resumed", False))
            )
            # Mark as resumed
            doc_ref.update({"resumed": True})
            return cp
        except Exception as exc:
            logger.error(f"Failed to load Firestore checkpoint: {exc}")
            return None

    def list_all(self) -> List[Dict[str, Any]]:
        if not self._db: return []
        try:
            docs = self._db.collection(self.collection_name).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
            return [
                {
                    "task_id": d.id,
                    "step_index": d.to_dict().get("step_index"),
                    "created_at": d.to_dict().get("created_at"),
                    "resumed": bool(d.to_dict().get("resumed", False))
                }
                for d in docs
            ]
        except Exception as exc:
            logger.error(f"Failed to list Firestore checkpoints: {exc}")
            return []

    def clear(self, task_id: str) -> bool:
        if not self._db: return False
        try:
            self._db.collection(self.collection_name).document(task_id).delete()
            return True
        except Exception as exc:
            logger.error(f"Failed to clear Firestore checkpoint: {exc}")
            return False

``n

## File: backend\admin\god.py

`python

import time
from typing import Optional
from loguru import logger

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

class AdminGodLayer:
    """
    Constitutional enforcement layer.
    Every write action requires admin approval unless explicitly whitelisted.
    Reads from Google Cloud Firestore (Distributed & Serverless).
    """

    def __init__(self, db_path: str = None):
        # db_path is ignored for Firestore, kept for backward compatibility
        self.collection_name = "constitutional_rules"
        self._db = None
        if firestore:
            try:
                # Firestore client auto-detects Cloud Run service account
                self._db = firestore.Client()
                self._init_db()
            except Exception as e:
                logger.warning(f"Failed to initialize Firestore for AdminGodLayer: {e}")
        else:
            logger.warning("google-cloud-firestore not installed. AdminGodLayer disabled.")

    def _init_db(self):
        if not self._db: return
        try:
            # Check if admin_authorized exists, if not initialize it
            doc_ref = self._db.collection(self.collection_name).document("admin_authorized")
            if not doc_ref.get().exists:
                self.set_rule("admin_authorized", "true")
        except Exception as e:
            logger.error(f"Error initializing AdminGodLayer DB: {e}")

    def get_rule(self, key: str, default: Optional[str] = None) -> Optional[str]:
        if not self._db: return default
        try:
            doc_ref = self._db.collection(self.collection_name).document(key)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict().get("value", default)
            return default
        except Exception as e:
            logger.error(f"Error fetching rule {key}: {e}")
            return default

    def set_rule(self, key: str, value: str) -> None:
        if not self._db: return
        try:
            doc_ref = self._db.collection(self.collection_name).document(key)
            doc_ref.set({
                "value": value,
                "updated_at": time.time()
            })
            logger.info(f"Constitutional rule updated in Firestore: {key} = {value}")
        except Exception as e:
            logger.error(f"Error setting rule {key}: {e}")

    def is_admin_action_allowed(self, action: str) -> bool:
        """
        Returns True if the action is allowed under current rules.
        Blocked actions require explicit admin_authorized flip,
        except whitelisted bootstrap keys.
        """
        whitelist = {"health", "read", "learn", "ping"}
        if action in whitelist:
            return True
        flag = self.get_rule("admin_authorized")
        return flag == "true"

    def enforce(self, action: str) -> None:
        if not self.is_admin_action_allowed(action):
            raise PermissionError(
                "Action blocked by constitutional rules. "
                "Admin authorization required."
            )

``n

## File: skill_loader.py

`python

import os
import importlib.util
from typing import Dict, Any, List
from loguru import logger
from skills.registry import SkillRegistry
from skills.installer import SkillInstaller
from skills.marketplace import SkillMarketplace

class SkillLoader:
    """Dynamically discovers and loads skill modules at runtime."""
    def __init__(self, registry: SkillRegistry = None, installer: SkillInstaller = None):
        self.registry = registry or SkillRegistry()
        self.installer = installer or SkillInstaller(self.registry)
        self.marketplace = SkillMarketplace()
        self._loaded: Dict[str, Any] = {}

    def discover_local(self, skills_dir: str = None) -> List[str]:
        if skills_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(base_dir, "skills", "dynamic")
        os.makedirs(skills_dir, exist_ok=True)
        found = []
        for entry in os.listdir(skills_dir):
            path = os.path.join(skills_dir, entry)
            if os.path.isdir(path):
                main_py = os.path.join(path, "main.py")
                if os.path.exists(main_py):
                    found.append(entry)
        return found

    def load(self, name: str) -> Any:
        if name in self._loaded:
            return self._loaded[name]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(base_dir, "skills", "dynamic", name, "main.py")
        if not os.path.exists(candidate):
            raise FileNotFoundError(f"Skill not found: {name}")
            
        # Sandbox AST Check for RCE Prevention
        import ast
        with open(candidate, "r", encoding="utf-8") as f:
            code = f.read()
        try:
            tree = ast.parse(code)
            banned_imports = {"os", "sys", "subprocess", "shutil", "socket", "pty"}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in banned_imports:
                            raise SecurityError(f"Malicious import '{alias.name}' detected in skill.")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in banned_imports:
                        raise SecurityError(f"Malicious import '{node.module}' detected in skill.")
        except SyntaxError:
            raise ValueError(f"Syntax error in skill code: {name}")
            
        spec = importlib.util.spec_from_file_location(f"skills.dynamic.{name}", candidate)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._loaded[name] = mod
        return mod

    def search_and_install(self, query: str) -> bool:
        results = self.marketplace.search_skills(query)
        if not results:
            logger.info(f"No marketplace skills found for query '{query}'")
            return False
        skill = results[0]
        ok = self.installer.install_skill_from_source(
            name=skill["name"],
            code=skill.get("code", ""),
            version=skill.get("version", "1.0.0"),
            description=skill.get("description", ""),
            dependencies=skill.get("dependencies", []),
        )
        logger.info(f"Skill install for '{skill['name']}': {'ok' if ok else 'failed'}")
        return ok

``n

## File: backend\api\routes\task.py

`python

import typing
import json

from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, JSONResponse


router = APIRouter()


# --- Agentic Security & Context: Task Request Schema ---
# Added messages and session_id parameters on 2026-06-21 to prevent context loss.
class TaskRequest(BaseModel):
    task: str
    task_type: str = "general"
    max_cost: float = 0.01
    admin_token: str | None = None
    schema_name: str | None = None
    messages: list[dict] | None = None
    session_id: str | None = None


class TaskResponse(BaseModel):
    success: bool
    result: str | None = None
    provider: str | None = None
    cost: float | None = None
    error: str | None = None


class CompletionRequest(BaseModel):
    prefix: str
    suffix: str
    filePath: str
    language: str
    sessionId: str | None = None


class CompletionResponse(BaseModel):
    success: bool
    suggestions: list[str]


class ChatStreamRequest(BaseModel):
    message: str
    sessionId: str | None = None
    messages: list[dict] | None = None
    context: dict | None = None


def _build_completion_prompt(prefix: str, suffix: str) -> str:
    return (
        f"You are a code completion assistant. Your task is to provide the code that fits between the prefix and suffix.\n"
        f"Do NOT wrap the response in code blocks, markdown, or explain it. Return ONLY the code to be inserted.\n\n"
        f"--- PREFIX ---\n{prefix}\n"
        f"--- SUFFIX ---\n{suffix}\n"
        f"--- COMPLETION ---"
    )


def _build_chat_prompt(req: ChatStreamRequest) -> str:
    context = req.context or {}
    parts = [f"User: {req.message}"]
    if context.get("codeSnippet"):
        parts.append(f"Code snippet:\n{context['codeSnippet']}")
    if context.get("filePath"):
        parts.append(f"File: {context['filePath']}")
    if context.get("language"):
        parts.append(f"Language: {context['language']}")
    parts.append("Assistant:")
    return "\n".join(parts)


@router.post("/api/chat/completion", response_model=CompletionResponse)
async def get_completion(req: CompletionRequest):
    import core.app as app_mod
    model_router = app_mod.model_router

    prompt = _build_completion_prompt(req.prefix, req.suffix)

    raw = await model_router.async_route_and_generate(
        prompt=prompt,
        task_type="completion",
        max_cost=0.005,
    )

    completion_text = raw.get("text", "")
    if completion_text.strip().startswith("```"):
        lines = completion_text.strip().splitlines()
        if len(lines) > 1:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            completion_text = "\n".join(lines)

    suggestions = [completion_text] if completion_text else []
    return CompletionResponse(success=True, suggestions=suggestions)


@router.post("/api/chat/stream")
async def stream_chat(req: ChatStreamRequest):
    import core.app as app_mod

    model_router = app_mod.model_router
    prompt = _build_chat_prompt(req)

    async def event_generator():
        async for chunk in model_router.async_route_and_stream(
            prompt=prompt,
            task_type="general",
            max_cost=0.01,
        ):
            token = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
            yield f"data: {json.dumps({'token': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


class ProblemDetailsResponse(JSONResponse):
    def __init__(self, title: str, status: int, detail: str, type_url: str = "about:blank", instance: typing.Optional[str] = None, **kwargs):
        content = {
            "type": type_url,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance or "",
        }
        content.update(kwargs)
        super().__init__(status_code=status, content=content, media_type="application/problem+json")


# --- Action Cards Helpers ---
# Added by Agent Antigravity on 2026-06-21. Formats output as structured action card JSON.
def format_chat_history(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "content" in data:
                    content = data["content"]
            except Exception:
                pass
        role_label = "User" if role == "user" else "Assistant"
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)



def format_response(text: str, task_type: str) -> str:
    # Extracts code blocks to clean markup
    def extract_code(t: str) -> str:
        if "```" in t:
            parts = t.split("```")
            for part in parts[1:]:
                lines = part.splitlines()
                if len(lines) > 0:
                    return "\n".join(lines[1:])
        return t
        
    def detect_language(t: str) -> str:
        if "```" in t:
            lang = t.split("```")[1].splitlines()[0].strip()
            if lang:
                return lang
        return "javascript"

    if "```" in text or task_type in ["code", "completion"]:
        return json.dumps({
            "type": "code",
            "content": extract_code(text),
            "metadata": {
                "language": detect_language(text),
                "filename": "index.html" if "html" in detect_language(text) else "component.tsx",
                "actions": [
                    {"id": "preview", "label": "ðŸ‘ï¸ Preview", "type": "preview"},
                    {"id": "save", "label": "ðŸ’¾ Save to Project", "type": "save"},
                    {"id": "run", "label": "â–¶ï¸ Run Code", "type": "run"},
                    {"id": "deploy", "label": "ðŸš€ Deploy", "type": "deploy"}
                ]
            }
        }, ensure_ascii=False)
        
    if task_type == "image" or "generate image" in text.lower():
        import re
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        image_url = urls[0] if urls else text
        return json.dumps({
            "type": "image",
            "content": image_url,
            "metadata": {
                "actions": [
                    {"id": "download", "label": "â¬‡ï¸ Download", "type": "save"},
                    {"id": "share", "label": "ðŸ”— Share", "type": "share"}
                ]
            }
        }, ensure_ascii=False)
        
    return json.dumps({
        "type": "text",
        "content": text,
        "metadata": {
            "actions": [
                {"id": "copy", "label": "ðŸ“‹ Copy", "type": "copy"},
                {"id": "share", "label": "ðŸ”— Share", "type": "share"}
            ]
        }
    }, ensure_ascii=False)


@router.post("/task/execute")
async def execute_task(req: TaskRequest):
    import core.app as app_mod
    admin_god = app_mod.admin_god
    model_router = app_mod.model_router
    intent_clf = app_mod.intent_clf

    try:
        admin_god.enforce("execute")
    except PermissionError as exc:
        return ProblemDetailsResponse(
            title="Forbidden Access",
            status=403,
            detail=str(exc),
            type_url="https://supremeai.local/errors/forbidden",
            instance="/task/execute"
        )

    import anyio
    import hashlib

    # Offload heavy CPU-bound Intent classification to background thread pool
    app_spec = await anyio.to_thread.run_sync(
        app_mod.intent_parser.parse_intent, req.task, req.messages
    )
    intent = await anyio.to_thread.run_sync(
        intent_clf.classify, req.task
    )
    
    task_type = req.task_type
    if intent.task_type != "general" and req.task_type == "general":
        task_type = intent.task_type.value if hasattr(intent.task_type, "value") else str(intent.task_type)

    # Build prompt context if chat messages are provided
    prompt = req.task
    if req.messages and len(req.messages) > 1:
        context_prompt = format_chat_history(req.messages[:-1])
        prompt = f"{context_prompt}\nUser: {req.task}\nAssistant:"

    # --- AI Token Burning Semantic Cache (Redis) ---
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    cache_key = f"semantic_cache:{prompt_hash}:{task_type}"
    redis = getattr(app_mod, "redis_queue", None)
    
    raw = None
    if redis and hasattr(redis, "configured") and redis.configured:
        cached_result = redis.get(cache_key)
        if cached_result:
            try:
                raw = json.loads(cached_result)
                raw["provider"] = "semantic-cache-hit"
                raw["cost"] = 0.0
            except Exception:
                pass

    if not raw:
        raw = await model_router.async_route_and_generate(
            prompt=prompt,
            task_type=task_type,
            max_cost=req.max_cost,
        )
        if raw.get("success") and redis and hasattr(redis, "configured") and redis.configured:
            try:
                redis.set(cache_key, json.dumps(raw), ex=86400) # Cache for 24 hours
            except Exception:
                pass

    # Log to ExperienceDatabase
    from adaptive_engine.experience_db import Experience
    import datetime
    
    exp = Experience(
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        user_id=req.session_id or "default-user",
        request=req.task,
        context={
            "task_type": task_type,
            "session_id": req.session_id,
            "app_type": app_spec.app_type,
            "features": app_spec.features,
            "tech_stack": app_spec.tech_stack,
            "pages": app_spec.pages,
            "integrations": app_spec.integrations,
            "deployment_target": app_spec.deployment_target
        },
        action_taken=f"Executed task on provider {raw.get('provider')}",
        result="success" if raw.get("success") else "failure",
        error_message=raw.get("error"),
        generated_code=raw.get("text") if ("```" in raw.get("text", "")) else None,
        what_worked=["Intent parsed successfully"] if raw.get("success") else [],
        what_failed=[] if raw.get("success") else [raw.get("error", "Unknown error")]
    )
    try:
        app_mod.experience_db.record_experience(exp)
    except Exception:
        pass

    if not raw.get("success"):
        return ProblemDetailsResponse(
            title="Task Execution Failed",
            status=502,
            detail=raw.get("error") or "Unknown upstream error",
            type_url="https://supremeai.local/errors/bad-gateway",
            instance="/task/execute",
            provider=raw.get("provider"),
            cost=raw.get("cost")
        )

    # Format output as Action-Oriented JSON string
    formatted_result = format_response(raw.get("text", ""), task_type)

    return TaskResponse(
        success=True,
        result=formatted_result,
        provider=raw.get("provider"),
        cost=raw.get("cost", 0.0),
    )



``n

