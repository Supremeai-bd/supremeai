from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from memory.checkpoint_resume import CheckpointResume
from memory.sliding_window import SlidingWindowMemory, SlidingWindowConfig

router = APIRouter(prefix="/memory", tags=["memory"])

_checkpoint: Optional[CheckpointResume] = None
_window: Optional[SlidingWindowMemory] = None


def get_checkpoint() -> CheckpointResume:
    global _checkpoint
    if _checkpoint is None:
        _checkpoint = CheckpointResume()
    return _checkpoint


def get_window() -> SlidingWindowMemory:
    global _window
    if _window is None:
        _window = SlidingWindowMemory()
    return _window


class CheckpointSaveRequest(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    step_index: int = Field(..., ge=0)
    state: Dict[str, Any] = Field(default_factory=dict)


class CheckpointResponse(BaseModel):
    task_id: str
    step_index: int
    state: Dict[str, Any]
    resumed: bool


class ChunkRequest(BaseModel):
    text: str
    session_id: str = "default"
    max_tokens: int = 4000
    overlap_ratio: float = 0.15


class ChunkResponse(BaseModel):
    session_id: str
    windows: List[Dict[str, Any]]


class ContextRequest(BaseModel):
    documents: List[str] = Field(default_factory=list)
    query: str = ""
    session_id: str = "default"
    budget: Optional[int] = None


class ContextResponse(BaseModel):
    session_id: str
    context: str


@router.post("/checkpoint", response_model=CheckpointResponse)
def save_checkpoint(payload: CheckpointSaveRequest):
    store = get_checkpoint()
    ok = store.save(payload.task_id, payload.step_index, payload.state)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save checkpoint")
    return CheckpointResponse(task_id=payload.task_id, step_index=payload.step_index, state=payload.state, resumed=False)


@router.get("/checkpoint/{task_id}", response_model=Optional[CheckpointResponse])
def load_checkpoint(task_id: str):
    store = get_checkpoint()
    result = store.load(task_id)
    if not result:
        return None
    return CheckpointResponse(**result)


@router.get("/checkpoints", response_model=List[Dict[str, Any]])
def list_checkpoints():
    store = get_checkpoint()
    return store.list_all()


@router.delete("/checkpoint/{task_id}")
def clear_checkpoint(task_id: str):
    store = get_checkpoint()
    ok = store.clear(task_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to clear checkpoint")
    return {"status": "ok", "task_id": task_id}


@router.post("/chunk", response_model=ChunkResponse)
def chunk_text(payload: ChunkRequest):
    config = SlidingWindowConfig(max_tokens=payload.max_tokens, overlap_ratio=payload.overlap_ratio)
    memory = SlidingWindowMemory(config=config)
    windows = memory.chunk(payload.text, session_id=payload.session_id)
    return ChunkResponse(session_id=payload.session_id, windows=windows)


@router.post("/context", response_model=ContextResponse)
def build_context(payload: ContextRequest):
    config = SlidingWindowConfig()
    memory = SlidingWindowMemory(config=config)
    budget = payload.budget or config.max_tokens
    context = memory.build_context(payload.documents, payload.query, payload.session_id, budget)
    return ContextResponse(session_id=payload.session_id, context=context)


@router.get("/recall", response_model=List[Dict[str, Any]])
def recall_memory(session_id: str = "default", limit: int = 20):
    memory = get_window()
    return memory.recall(session_id, limit=limit)


@router.delete("/recall")
def clear_memory(session_id: str = "default"):
    memory = get_window()
    ok = memory.clear(session_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to clear memory")
    return {"status": "ok", "session_id": session_id}
