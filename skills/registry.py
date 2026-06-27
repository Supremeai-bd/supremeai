import os
import json
from typing import Optional, Dict, Any, List

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
        
    def register_skill(self, name: str, version: str, description: str, entry_point: str, dependencies: List[str] = [], uss: Optional[Dict[str, Any]] = None) -> bool:
        if uss:
            from skills.schema import UniversalSkillSchema
            try:
                UniversalSkillSchema(**uss)
            except Exception as e:
                from loguru import logger
                logger.error(f"USS validation failed for skill '{name}': {e}")
                return False

        # Attempt to store in Supabase DB first
        try:
            from database.supabase_client import db
            if db.client:
                db.upsert_db_skill({
                    "name": name,
                    "version": version,
                    "description": description,
                    "category": uss.get("category", "general") if uss else "general",
                    "parameters_schema": uss.get("parameters", {}) if uss else {},
                    "metadata": uss or {}
                })
        except Exception as e:
            from loguru import logger
            logger.debug(f"Failed to register skill '{name}' to Supabase: {e}")

        # Store in local registry fallback
        self.skills["skills"][name] = {
            "name": name,
            "version": version,
            "description": description,
            "entry_point": entry_point,
            "dependencies": dependencies,
            "uss": uss
        }
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self.skills, f, indent=4)
            return True
        except Exception:
            return False
            
    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        # Attempt to retrieve from Supabase DB first
        try:
            from database.supabase_client import db
            if db.client:
                skill_data = db.get_db_skill(name)
                if skill_data:
                    return {
                        "name": skill_data.get("name"),
                        "version": skill_data.get("version"),
                        "description": skill_data.get("description"),
                        "entry_point": f"skills.dynamic.{name}",
                        "dependencies": [],
                        "uss": skill_data.get("metadata")
                    }
        except Exception as e:
            from loguru import logger
            logger.debug(f"Failed to fetch skill '{name}' from Supabase: {e}")

        # Local fallback
        return self.skills["skills"].get(name)
