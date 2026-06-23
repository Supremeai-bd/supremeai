import subprocess
import os
from typing import Dict, Any
from loguru import logger

class ComputerAgent:
    """Safely executes local commands and handles filesystem operations."""
    def __init__(self):
        pass
        
    def execute_command(self, cmd: str) -> Dict[str, Any]:
        logger.info(f"Executing system command: '{cmd}'")
        
        # Basic safety check
        unsafe_keywords = ["rm -rf", "format", "del /s", "mkfs", "shutdown"]
        if any(kw in cmd for kw in unsafe_keywords):
            logger.warning(f"Unsafe command blocked: '{cmd}'")
            return {
                "success": False,
                "error": "Security block: Unsafe command keywords detected."
            }
            
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15.0
            )
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timeout expired"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    def read_file(self, filepath: str) -> Dict[str, Any]:
        if not os.path.exists(filepath):
            return {"success": False, "error": "File does not exist"}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return {"success": True, "content": f.read()}
        except Exception as e:
            return {"success": False, "error": str(e)}
