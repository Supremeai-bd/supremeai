import os
import subprocess
from typing import Any, Dict
from loguru import logger

class DockerSandbox:
    def __init__(self, image: str = "python:3.10-slim"):
        self.image = image
        self.docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        try:
            # Check if docker daemon is running
            res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=3)
            return res.returncode == 0
        except Exception:
            return False

    def execute_command(self, cmd: str) -> Dict[str, Any]:
        """Runs a command inside a sandboxed Docker container."""
        # RCE/Prompt Injection Pre-flight Firewall Check
        harmful_keywords = ["rm -rf", "mkfs", "dd if=", "shutdown", "reboot", ":(){ :|:& };:"]
        forbidden_patterns = [
            "environ", "getenv", "getenvb", "os.environ",
            "curl", "wget", "socket", "requests", "urllib", "httpx", "http.client",
            "nc ", "netcat", "bash -i", "/dev/tcp", "/dev/udp",
            "eval(", "exec(", "subprocess", "system("
        ]
        
        cmd_lower = cmd.lower()
        if any(kw in cmd_lower for kw in harmful_keywords) or any(pat in cmd_lower for pat in forbidden_patterns):
            logger.warning("Security Firewall: Command blocked due to high-risk pattern.")
            return {"success": False, "error": "Security Firewall block: command contains forbidden patterns."}

        if not self.docker_available:
            if os.getenv("ALLOW_LOCAL_SANDBOX_FALLBACK") != "true":
                logger.error("Docker is not available and local execution fallback is disabled.")
                return {"success": False, "error": "Sandbox execution failed: Docker is not running and local execution is disabled for safety."}

            logger.warning("Docker is not available. Simulating command execution in local process.")
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                return {
                    "success": res.returncode == 0,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                    "exit_code": res.returncode,
                    "simulated": True
                }
            except Exception as e:
                return {"success": False, "error": str(e), "simulated": True}

        # Run command securely inside docker
        try:
            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none", # Sandbox: no internet
                self.image,
                "sh", "-c", cmd
            ]
            res = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=10)
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "simulated": False
            }
        except Exception as e:
            return {"success": False, "error": str(e), "simulated": False}
