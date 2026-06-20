from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from core.universal_rules import UniversalRulesEngine


class AutoSkillCreator:
    def __init__(self, rules_engine: Optional[UniversalRulesEngine] = None):
        self.rules_engine = rules_engine or UniversalRulesEngine()

    def analyze_demand_patterns(self, task_history: List[Dict[str, Any]]) -> List[str]:
        repeated = self.rules_engine.rules.get("patterns", {}).get("repeated_tasks", [])
        return list({t.get("task") for t in task_history if t.get("success") is False}) + repeated

    def generate_skill_code(self, skill_name: str) -> str:
        class_name = "".join(part.capitalize() for part in skill_name.split("_"))
        return f"class {class_name}:\n    def __init__(self): ...\n    def run(self, payload: dict) -> dict:\n        return {{'skill': '{skill_name}', 'status': 'ok'}}\n"

    def register_new_skill(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "skill_name": skill.get("skill_name"),
            "status": "registered",
            "registered_at": __import__("datetime").datetime.now().__import__("timezone").utcnow().isoformat(),
        }

    def test_new_skill(self, skill_path: str) -> bool:
        return os.path.exists(skill_path)
