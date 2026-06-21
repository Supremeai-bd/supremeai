from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from loguru import logger


class VideoGenerator:
    def __init__(
        self,
        runway_api_key: Optional[str] = None,
        kling_api_key: Optional[str] = None,
    ) -> None:
        self.runway_api_key = runway_api_key or os.getenv("RUNWAY_API_KEY", "")
        self.kling_api_key = kling_api_key or os.getenv("KLING_API_KEY", "")

    @staticmethod
    def _runway_payload(prompt: str, duration: int) -> Dict[str, Any]:
        return {
            "prompt": prompt,
            "duration": duration,
            "model": "gen-3-alpha",
        }

    @staticmethod
    def _kling_payload(prompt: str, duration: int) -> Dict[str, Any]:
        return {
            "prompt": prompt,
            "duration": duration,
            "mode": "standard",
            "aspect_ratio": "16:9",
        }

    def _call_runway(self, prompt: str, duration: int) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.runway_api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }
        url = "https://api.runwayml.com/v1/generate"
        payload = self._runway_payload(prompt, duration)
        with httpx.Client(timeout=120.0) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            job_id = data.get("id")
            
            if not job_id:
                raise RuntimeError("Failed to retrieve Runway job ID from response.")

            # Polling loop for async completion
            import time
            task_url = f"https://api.runwayml.com/v1/tasks/{job_id}"
            video_url = None
            max_retries = 60
            poll_interval = 10
            for i in range(max_retries):
                logger.info(f"Polling Runway task {job_id} (attempt {i+1}/{max_retries})...")
                res_get = client.get(task_url, headers=headers)
                res_get.raise_for_status()
                task_data = res_get.json()
                status = task_data.get("status")
                
                if status == "SUCCEEDED":
                    outputs = task_data.get("output", [])
                    if outputs:
                        video_url = outputs[0]
                    break
                elif status == "FAILED":
                    raise RuntimeError(f"Runway task failed: {task_data.get('failure')}")
                time.sleep(poll_interval)
            
            if not video_url:
                raise TimeoutError("Runway video generation timed out.")

        return {
            "success": True,
            "provider": "runway",
            "prompt": prompt,
            "duration": duration,
            "job_id": job_id,
            "video_url": video_url,
            "mock": False,
        }

    def _call_kling(self, prompt: str, duration: int) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.kling_api_key}",
            "Content-Type": "application/json",
        }
        url = "https://api.klingai.ai/v1/videos/generate"
        payload = self._kling_payload(prompt, duration)
        with httpx.Client(timeout=120.0) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            job_id = data.get("data", {}).get("task_id")

            if not job_id:
                raise RuntimeError("Failed to retrieve Kling task ID from response.")

            # Polling loop for async completion
            import time
            task_url = f"https://api.klingai.ai/v1/videos/generate/{job_id}"
            video_url = None
            max_retries = 60
            poll_interval = 10
            for i in range(max_retries):
                logger.info(f"Polling Kling task {job_id} (attempt {i+1}/{max_retries})...")
                res_get = client.get(task_url, headers=headers)
                res_get.raise_for_status()
                task_data = res_get.json()
                
                inner_data = task_data.get("data", {})
                status = inner_data.get("task_status") or inner_data.get("status") or task_data.get("status")
                
                if status in ("succeed", "completed", "SUCCESS", "SUCCEEDED"):
                    result = inner_data.get("task_result") or inner_data.get("result") or {}
                    videos = result.get("videos", [])
                    if videos and isinstance(videos, list):
                        video_url = videos[0].get("url")
                    else:
                        video_url = result.get("url") or inner_data.get("url")
                    break
                elif status in ("failed", "FAILED"):
                    raise RuntimeError(f"Kling task failed: {inner_data.get('task_status_msg') or inner_data.get('message')}")
                time.sleep(poll_interval)

            if not video_url:
                raise TimeoutError("Kling video generation timed out.")

        return {
            "success": True,
            "provider": "kling",
            "prompt": prompt,
            "duration": duration,
            "job_id": job_id,
            "video_url": video_url,
            "mock": False,
        }

    def generate(
        self,
        prompt: str,
        duration: int = 5,
        provider: str = "auto",
        output_path: Optional[str] = None,
        tried: Optional[set] = None,
    ) -> Dict[str, Any]:
        tried = tried or set()
        if provider == "auto":
            if self.runway_api_key and "runway" not in tried:
                provider = "runway"
            elif self.kling_api_key and "kling" not in tried:
                provider = "kling"

        if provider == "runway":
            if not self.runway_api_key:
                logger.warning("Runway selected but RUNWAY_API_KEY is missing. Returning stub payload.")
                return self._stub(prompt, duration, "runway", output_path=output_path)
            try:
                return self._call_runway(prompt, duration)
            except Exception as exc:
                logger.error(f"Runway failed: {exc}")
                if self.kling_api_key and "kling" not in tried:
                    logger.info("Falling back to Kling provider.")
                    return self.generate(prompt=prompt, duration=duration, provider="kling", output_path=output_path, tried={*tried, "runway"})
                return self._stub(prompt, duration, "runway", output_path=output_path, error=str(exc))

        if provider == "kling":
            if not self.kling_api_key:
                logger.warning("Kling selected but KLING_API_KEY is missing. Returning stub payload.")
                return self._stub(prompt, duration, "kling", output_path=output_path)
            try:
                return self._call_kling(prompt, duration)
            except Exception as exc:
                logger.error(f"Kling failed: {exc}")
                if self.runway_api_key and "runway" not in tried:
                    logger.info("Falling back to Runway provider.")
                    return self.generate(prompt=prompt, duration=duration, provider="runway", output_path=output_path, tried={*tried, "kling"})
                return self._stub(prompt, duration, "kling", output_path=output_path, error=str(exc))

        raise ValueError(f"Unknown provider: {provider!r}. Use 'runway', 'kling', or 'auto'.")

    @staticmethod
    def _stub(prompt: str, duration: int, provider: str, output_path: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        logger.info(f"Returning stub video payload for provider={provider}.")
        manifest = {
            "success": True,
            "provider": f"{provider}-stub",
            "prompt": prompt,
            "duration": duration,
            "job_id": "stub-job",
            "video_url": None,
            "mock": True,
            "error": error,
        }
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            manifest["output_path"] = str(path)
        return manifest
