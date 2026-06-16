import os
import json
import sys
from typing import Dict, Any
from loguru import logger

class HealthChecker:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(base_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)

    def run_health_check(self) -> Dict[str, Any]:
        """Validates the system imports, databases, and configuration status."""
        logger.info("Running daily system health check...")
        
        # 1. Dependency imports validation
        dependencies = ["fastapi", "pydantic", "sqlite3", "sympy", "matplotlib", "PIL", "chromadb"]
        dep_status = {}
        for dep in dependencies:
            try:
                __import__(dep)
                dep_status[dep] = "OK"
            except ImportError:
                dep_status[dep] = "MISSING"

        # 2. Key configuration checks
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_exists = os.path.exists(os.path.join(base_dir, ".env"))
        db_exists = os.path.exists(os.path.join(base_dir, "data", "supreme_memory.db"))

        overall_status = "HEALTHY"
        if "MISSING" in dep_status.values() or not env_exists:
            overall_status = "WARNING"

        report = {
            "overall_status": overall_status,
            "dependencies": dep_status,
            "env_file_configured": env_exists,
            "sqlite_db_exists": db_exists,
            "python_version": sys.version,
        }

        # Save report
        report_path = os.path.join(self.data_dir, "health_status.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=4)
            logger.info(f"Health report successfully written to {report_path}")
        except Exception as e:
            logger.error(f"Failed to write health report: {e}")

        return report
