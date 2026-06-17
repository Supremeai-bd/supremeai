from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from tools.image_generator import HFImageGenerator
from tools.video_generator import VideoGenerator

router = APIRouter(prefix="/api/media", tags=["media"])
image_generator = HFImageGenerator()
video_generator = VideoGenerator()


class ImageRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    output_path: Optional[str] = "data/generated_image.png"


class VideoRequest(BaseModel):
    prompt: str
    duration: Optional[int] = 5
    provider: Optional[str] = "auto"
    output_path: Optional[str] = "data/generated_video.mp4"


class MediaResponse(BaseModel):
    success: bool
    provider: str
    prompt: str
    output_path: str
    mock: bool
    duration: Optional[int] = None
    error: Optional[str] = None


@router.post("/generate/image", response_model=MediaResponse)
async def generate_image(req: ImageRequest):
    result = image_generator.generate_image(req.prompt, model=req.model, output_path=req.output_path)
    return MediaResponse(
        success=result.get("success", False),
        provider=result.get("model", result.get("provider", "")),
        prompt=req.prompt,
        output_path=result.get("output_path", req.output_path),
        mock=result.get("mock", False),
        error=result.get("error"),
    )


@router.post("/generate/video", response_model=MediaResponse)
async def generate_video(req: VideoRequest):
    result = video_generator.generate(req.prompt, duration=req.duration, provider=req.provider)
    return MediaResponse(
        success=result.get("success", False),
        provider=result.get("provider", ""),
        prompt=req.prompt,
        output_path=result.get("output_path", req.output_path),
        mock=result.get("mock", False),
        duration=result.get("duration", req.duration),
        error=result.get("error"),
    )
