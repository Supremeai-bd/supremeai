from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from brain.model_router import ModelRouter

router = APIRouter(prefix="/api/stream", tags=["stream"])
model_router = ModelRouter()


class StreamRequest(BaseModel):
    prompt: str
    task_type: str = "general"
    max_cost: float = 0.01


@router.post("/chat")
def stream_chat(req: StreamRequest):
    from fastapi.responses import StreamingResponse

    def event_generator():
        for chunk in model_router.route_and_stream(
            prompt=req.prompt,
            task_type=req.task_type,
            max_cost=req.max_cost,
        ):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/plain")
