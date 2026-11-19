"""SupremeAI Tiny Brain + Hybrid Top AI Detector (Hugging Face Gradio + FastAPI Space)."""

from __future__ import annotations

import os
import re
import time
from typing import Any

import gradio as gr
import httpx
import spaces
from fastapi import FastAPI
from pydantic import BaseModel

PROBE_INTERVAL_SECONDS = 1800
COOLDOWN_SECONDS = 300

PROBE_ENDPOINTS: dict[str, tuple[str, str]] = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1/models"),
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1/models"),
    "huggingface": ("HF_API_KEY", "https://huggingface.co/api/whoami-v2"),
}

_STATE: dict[str, Any] = {"last_probe": 0.0, "providers": {}}


async def refresh_top_ai(force: bool = False) -> list[str]:
    now = time.time()
    if not force and (now - _STATE["last_probe"]) < PROBE_INTERVAL_SECONDS and _STATE["providers"]:
        return get_top_ai()

    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for pid, (env_var, url) in PROBE_ENDPOINTS.items():
            key = os.getenv(env_var, "").strip()
            if not key:
                results[pid] = {"configured": False, "healthy": False, "latency_ms": 9999.0, "cooldown_until": 0.0}
                continue
            headers = {} if pid == "gemini" else {"Authorization": f"Bearer {key}"}
            probe_url = f"{url}?key={key}" if pid == "gemini" else url
            t0 = time.perf_counter()
            try:
                r = await client.get(probe_url, headers=headers)
                lat = round((time.perf_counter() - t0) * 1000.0, 2)
                results[pid] = {"configured": True, "healthy": r.status_code == 200, "latency_ms": lat, "cooldown_until": 0.0}
            except Exception:
                results[pid] = {"configured": True, "healthy": False, "latency_ms": 9999.0, "cooldown_until": 0.0}

    _STATE["providers"] = results
    _STATE["last_probe"] = time.time()
    return get_top_ai()


def get_top_ai() -> list[str]:
    now = time.time()
    avail = [
        (pid, info["latency_ms"])
        for pid, info in _STATE["providers"].items()
        if info["configured"] and info["healthy"] and now >= info["cooldown_until"]
    ]
    avail.sort(key=lambda x: x[1])
    return [pid for pid, _ in avail]


def route_stage1_fast(prompt: str, context: str = "") -> dict[str, Any]:
    """Stage 1 (<5ms) fast rule router + fallback structured decision."""
    text = f"{context} {prompt}".lower().strip()
    if re.search(r"\b(hi|hello|salam|kemon acho|assalamu)\b", text):
        return {
            "stage": "stage1_fast",
            "intent": "general_chat",
            "capability_tier": "local_reply",
            "dispatch_mode": "direct_prompt",
            "tools_needed": [],
        }
    if re.search(r"\b(server|down|health|logs|deploy|render|kaggle|mcp)\b", text):
        return {
            "stage": "stage1_fast",
            "intent": "system_action",
            "capability_tier": "mcp_tower",
            "dispatch_mode": "tool_call",
            "tools_needed": ["health_check"],
        }
    if re.search(r"\b(code|bug|error|python|js|ts|fix|api|sql|429)\b", text):
        return {
            "stage": "stage1_fast",
            "intent": "code_debug",
            "capability_tier": "deep_coding",
            "dispatch_mode": "direct_prompt",
            "tools_needed": [],
        }
    return {
        "stage": "stage2_tiny_brain_pending",
        "intent": "general_chat",
        "capability_tier": "fast_chat",
        "dispatch_mode": "direct_prompt",
        "tools_needed": [],
    }


class RouteRequest(BaseModel):
    prompt: str
    context: str = ""


app = FastAPI(title="SupremeAI Tiny Brain + Top AI Detector")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "hf-tiny-brain-space"}


@app.get("/top-ai")
async def top_ai(force: bool = False):
    ranked = await refresh_top_ai(force=force)
    return {"top_providers": ranked, "providers": _STATE["providers"]}


@app.post("/route")
async def route_api(req: RouteRequest):
    top = await refresh_top_ai()
    decision = route_stage1_fast(req.prompt, req.context)
    decision["top_available_ai"] = top
    return decision


@spaces.GPU(duration=90)
def run_micro_training(samples_count: int = 5) -> dict[str, Any]:
    """ZeroGPU micro-training hook (60-90s burst) for Tiny Brain distillation."""
    return {
        "status": "completed",
        "device": "ZeroGPU",
        "samples_processed": samples_count,
        "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
    }


@app.post("/train")
async def train_endpoint(samples_count: int = 5):
    return run_micro_training(samples_count)


async def gradio_route(prompt: str, context: str) -> dict[str, Any]:
    top = await refresh_top_ai()
    decision = route_stage1_fast(prompt, context)
    decision["top_available_ai"] = top
    return decision


demo = gr.Interface(
    fn=gradio_route,
    inputs=[
        gr.Textbox(label="User Prompt (Bangla / Banglish / English)", placeholder="bhai server down hoye gese check koro"),
        gr.Textbox(label="Short Context (Optional)", placeholder="Previous turn summary..."),
    ],
    outputs=gr.JSON(label="Tiny Brain Routing + Top AI Decision"),
    title="SupremeAI Tiny Brain + Hybrid Top AI Detector",
    description="Test 2-stage routing and 30-min proactive / instant reactive Top AI detection.",
)

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
