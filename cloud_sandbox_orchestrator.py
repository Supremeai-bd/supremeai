#!/usr/bin/env python3
"""
Cloud Sandbox Orchestrator
==========================

Manages ephemeral but persistent cloud environments (VMs/pods) for complex,
long-running AI tasks.
Integrates 'Freebuff CLI' as a zero-cost headless AI worker.
"""

import os
import httpx
import asyncio
from loguru import logger
from typing import Dict, Any, Optional


class CloudSandboxOrchestrator:
    """
    Orchestrates ephemeral cloud sandboxes (VMs) for code execution and delegates tasks to Freebuff.
    """

    def __init__(self, provider: str = "runpod"):
        self.provider = provider.lower()
        self.api_key = os.getenv(f"{self.provider.upper()}_API_KEY")
        
        self.base_url = self._get_base_url()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=60.0,
        )
        logger.info(f"Initialized CloudSandboxOrchestrator (Provider: {self.provider})")

    def _get_base_url(self) -> str:
        if self.provider == "runpod":
            return "https://api.runpod.io/v2"
        elif self.provider == "modal":
            return "https://api.modal.com"
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def create_sandbox(self, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("Cannot create sandbox: API key is missing. Running in mock/dry-run mode.")
            return {
                "id": "mock-sandbox-id-12345",
                "status": "running",
                "provider": self.provider,
                "mock": True
            }

        endpoint = self._get_endpoint("create")
        payload = self._prepare_creation_payload(spec)

        try:
            logger.info(f"Requesting new sandbox creation with spec: {spec}")
            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.success(f"Successfully created sandbox with ID: {data.get('id')}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create sandbox. Status: {e.response.status_code}, Body: {e.response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during sandbox creation: {e}")

        return None

    async def get_sandbox_status(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.info(f"Dry-run: Fetching status for sandbox {sandbox_id}")
            return {
                "id": sandbox_id,
                "status": "running",
                "provider": self.provider,
                "mock": True
            }

        endpoint = self._get_endpoint("status", sandbox_id)
        try:
            response = await self.client.get(endpoint)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get status for sandbox {sandbox_id}. Status: {e.response.status_code}")
        return None

    async def run_command(self, sandbox_id: str, command: str, timeout: int = 300) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            logger.info(f"Dry-run: Running command '{command}' in sandbox {sandbox_id}")
            return {
                "status": "COMPLETED",
                "exitCode": 0,
                "stdout": f"Mock output for execution of: {command}",
                "stderr": "",
                "mock": True
            }

        endpoint = self._get_endpoint("run", sandbox_id)
        payload = {"input": {"command": command, "timeout": timeout}}

        try:
            logger.info(f"Running command in sandbox {sandbox_id}: {command}")
            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to run command in sandbox {sandbox_id}. Status: {e.response.status_code}")
        return None

    async def destroy_sandbox(self, sandbox_id: str) -> bool:
        if not self.api_key:
            logger.warning(f"Dry-run: Destroying sandbox {sandbox_id}")
            return True

        endpoint = self._get_endpoint("destroy", sandbox_id)
        try:
            logger.warning(f"Destroying sandbox {sandbox_id}...")
            response = await self.client.post(endpoint)
            response.raise_for_status()
            logger.success(f"Sandbox {sandbox_id} destroyed successfully.")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to destroy sandbox {sandbox_id}. Status: {e.response.status_code}")
        return False

    # ------------------------------------------------------------------------
    # 🤖 FREEBUFF AI WORKER INTEGRATION
    # ------------------------------------------------------------------------
    async def delegate_to_freebuff(self, prompt: str, working_dir: str = ".") -> Dict[str, Any]:
        """
        বাংলা মন্তব্য: Freebuff CLI-কে অসিঙ্ক্রোনাস সাব-প্রসেস হিসেবে কল করে জিরো-কস্টে কোডিং টাস্ক এক্সিকিউট করা হচ্ছে।
        এটি SupremeAI-এর জন্য সম্পূর্ণ ফ্রি এআই ডেভেলপার হিসেবে কাজ করবে।
        """
        logger.info(f"🚀 Delegating task to Freebuff AI Worker in directory: {working_dir}")
        try:
            # বাংলা মন্তব্য: asyncio.create_subprocess_exec ব্যবহার করা হচ্ছে যাতে মূল ইভেন্ট লুপ ব্লক না হয়
            # উইন্ডোজের জন্য .cmd সাফিক্স হ্যান্ডলিং করা হয়েছে
            cmd = "freebuff.cmd" if os.name == "nt" else "freebuff"
            process = await asyncio.create_subprocess_exec(
                cmd, "--cwd", working_dir,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # প্রম্পট ইনপুট হিসেবে পাঠানো হচ্ছে
            stdout, stderr = await process.communicate(input=prompt.encode('utf-8'))
            
            if process.returncode == 0:
                logger.success("✅ Freebuff task completed successfully.")
                return {"status": "success", "output": stdout.decode('utf-8')}
            else:
                logger.error(f"❌ Freebuff task failed: {stderr.decode('utf-8')}")
                return {"status": "error", "error": stderr.decode('utf-8')}
                
        except FileNotFoundError:
            logger.error("🚨 Freebuff CLI not found. Please ensure it is installed globally (npm install -g freebuff).")
            return {"status": "error", "error": "Freebuff CLI not installed."}
        except Exception as e:
            logger.error(f"⚠️ Unexpected error running Freebuff: {e}")
            return {"status": "error", "error": str(e)}

    # --- Provider-specific helpers ---
    def _get_endpoint(self, action: str, sandbox_id: str = "") -> str:
        if self.provider == "runpod":
            endpoints = {
                "create": "/",
                "status": f"/{sandbox_id}",
                "run": f"/{sandbox_id}/run",
                "destroy": f"/{sandbox_id}/terminate",
            }
            return endpoints[action]
        raise NotImplementedError(f"Endpoints for provider '{self.provider}' not implemented.")

    def _prepare_creation_payload(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        if self.provider == "runpod":
            return {"pod": spec}
        raise NotImplementedError(f"Payload preparation for provider '{self.provider}' not implemented.")