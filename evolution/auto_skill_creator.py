from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


class AutoSkillCreator:
    def __init__(self, skills_root: Optional[str] = None) -> None:
        self.skills_root = Path(skills_root or os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills"))

    def create(self, name: str, description: str, template: Optional[str] = None) -> Dict[str, Any]:
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in (name or "new-skill")).strip("-").lower() or "new-skill"
        skill_dir = self.skills_root / safe_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        readme_path = skill_dir / "README.md"
        if not readme_path.exists():
            readme_path.write_text(f"# {name}\n\n{description or ''}\n", encoding="utf-8")
        plugin_path = skill_dir / "plugin.py"
        if not plugin_path.exists():
            plugin_path.write_text(
                "from __future__ import annotations\n\n\nclass Skill:\n    def __init__(self) -> None:\n        self.name = {name!r}\n\n    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:\n        return {{\"success\": True, \"skill\": self.name, \"payload\": payload}}\n".format(name=name),
                encoding="utf-8",
            )
        return {
            "success": True,
            "skill": safe_name,
            "path": str(skill_dir),
            "description": description,
            "files_created": [str(readme_path.relative_to(Path.cwd())), str(plugin_path.relative_to(Path.cwd()))],
        }
