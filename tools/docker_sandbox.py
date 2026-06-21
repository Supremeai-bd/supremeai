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
        # Simple security sanitization
        harmful_keywords = ["rm -rf", "mkfs", "dd if=", "shutdown", "reboot", ":(){ :|:& };:"]
        if any(kw in cmd for kw in harmful_keywords):
            return {"success": False, "error": "Security block: command contains forbidden patterns."}

        if not self.docker_available:
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
