import os
import json
from typing import Dict, Any, List
from loguru import logger

class SkillRegistry:
    """Manages metadata of installed skills."""
    def __init__(self, registry_path: str = None):
        if registry_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.registry_path = os.path.join(base_dir, "data", "skills_registry.json")
        else:
            self.registry_path = registry_path
            
        self.skills = self._load_registry()
        
    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        
        default_registry = {
            "skills": {}
        }
        
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(default_registry, f, indent=4)
        except Exception:
            pass
            
        return default_registry
        
    def register_skill(self, name: str, version: str, description: str, entry_point: str, dependencies: List[str] = []) -> bool:
        self.skills["skills"][name] = {
            "name": name,
            "version": version,
            "description": description,
            "entry_point": entry_point,
            "dependencies": dependencies
        }
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self.skills, f, indent=4)
            return True
        except Exception:
            return False
            
    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        # import Optional locally to keep signature simple
        from typing import Optional
        return self.skills["skills"].get(name)
