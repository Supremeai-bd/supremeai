import sys
import subprocess
from typing import List
from loguru import logger
from .registry import SkillRegistry

class SkillInstaller:
    """Installs dependencies and registers code packages as dynamic skills."""
    def __init__(self, registry: SkillRegistry = None, skills_dir: str = None):
        self.registry = registry or SkillRegistry()
        import os
        if skills_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.skills_dir = os.path.join(base_dir, "skills", "dynamic")
        else:
            self.skills_dir = skills_dir
        
    def install_dependencies(self, dependencies: List[str]) -> bool:
        """Executes pip to install missing libraries dynamically."""
        if not dependencies:
            return True
            
        logger.info(f"Dynamic Installer installing: {dependencies}")
        try:
            cmd = [sys.executable, "-m", "pip", "install"] + dependencies
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Installation completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e.stderr}")
            return False
            
    def install_skill_from_source(self, name: str, code: str, version: str, description: str, dependencies: List[str] = [], uss: dict = None) -> bool:
        """Writes custom skill code into the local skills workspace and registers it."""
        import os
        if uss:
            from skills.schema import UniversalSkillSchema
            try:
                UniversalSkillSchema(**uss)
            except Exception as e:
                logger.error(f"USS validation failed before installing skill '{name}': {e}")
                return False

        success = self.install_dependencies(dependencies)
        if not success:
            return False
            
        skill_dir = os.path.join(self.skills_dir, name)
        os.makedirs(skill_dir, exist_ok=True)
        
        entry_file = os.path.join(skill_dir, "main.py")
        try:
            with open(entry_file, "w", encoding="utf-8") as f:
                f.write(code)
            
            if uss:
                import json
                schema_file = os.path.join(skill_dir, "schema.json")
                with open(schema_file, "w", encoding="utf-8") as sf:
                    json.dump(uss, sf, indent=4)

            self.registry.register_skill(name, version, description, entry_file, dependencies, uss=uss)
            return True
        except Exception as e:
            logger.error(f"Error saving skill source code: {e}")
            return False
