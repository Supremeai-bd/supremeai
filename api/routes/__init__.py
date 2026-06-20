from .admin_dashboard import router as admin_dashboard_router
from .agent_tasks import agent_router as agent_router
from .auth import router as auth_router
from .browser import router as browser_router
from .codeflow import router as codeflow_router
from .feedback import router as feedback_router
from .knowledge import router as knowledge_router
from .marketplace import router as marketplace_router
from .media import router as media_router
from .memory import router as memory_router
from .metrics import router as metrics_router
from .simulator import router as simulator_router
from .stream import router as stream_router
from .task import router as task_router

__all__ = [
    "admin_dashboard_router",
    "agent_router",
    "auth_router",
    "browser_router",
    "codeflow_router",
    "feedback_router",
    "knowledge_router",
    "marketplace_router",
    "media_router",
    "memory_router",
    "metrics_router",
    "simulator_router",
    "stream_router",
    "task_router",
]
