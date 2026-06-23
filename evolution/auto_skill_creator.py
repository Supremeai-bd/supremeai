from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AutoSkillCreator:
    def __init__(self, rules_engine: Optional[Any] = None):
        self.rules_engine = rules_engine
        self.skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")

    def analyze_demand_patterns(self, task_history: List[Dict[str, Any]]) -> List[str]:
        pattern_source = []
        if self.rules_engine and hasattr(self.rules_engine, "rules"):
            pattern_source.extend(self.rules_engine.rules.get("patterns", {}).get("repeated_tasks", []))
        failed = list({t.get("task") for t in task_history if t.get("success") is False})
        return list(set(pattern_source + failed))

    def generate_skill_code(self, skill_name: str) -> str:
        class_name = "".join(part.capitalize() for part in skill_name.split("_"))
        return (
            f"class {class_name}:\n"
            f"    def __init__(self):\n"
            f"        self.name = \"{skill_name}\"\n\n"
            f"    def run(self, payload: dict) -> dict:\n"
            f"        return {{'skill': '{skill_name}', 'status': 'ok', 'result': payload}}\n"
        )

    def register_new_skill(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        skill_name = skill.get("skill_name", "unknown")
        filename = f"{skill_name}.py"
        code = skill.get("generated_code") or self.generate_skill_code(skill_name)
        os.makedirs(self.skills_dir, exist_ok=True)
        path = os.path.join(self.skills_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return {
            "skill_name": skill_name,
            "filenae": filename,
            "path": path,
            "status": "registered",
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_new_skill(self, skill_path: str) -> Dict[str, Any]:
        if not os.path.exists(skill_path):
            return {"passed": False, "reason": "file not found"}
        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", skill_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return {"passed": True, "skill_path": skill_path}
            return {"passed": False, "reason": result.stderr}
        except Exception as exc:
            return {"passed": False, "reason": str(exc)}

    def generate_from_failures(self, task_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        patterns = self.analyze_demand_patterns(task_history)
        created = []
        for pattern in patterns:
            proposal = {
                "skill_name": f"auto_{pattern.strip().replace(' ', '_').lower()}",
                "source_pattern": pattern,
                "generated_code": self.generate_skill_code(f"auto_{pattern.strip().replace(' ', '_').lower()}"),
                "status": "generated",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            registered = self.register_new_skill(proposal)
            tested = self.test_new_skill(registered["path"])
            registered["test_passed"] = tested.get("passed", False)
            registered["test_result"] = tested
            created.append(registered)
        return created
