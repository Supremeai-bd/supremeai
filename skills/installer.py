#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> installer.py
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> skills
# ============================================================================
import sys
import subprocess
from typing import List
from loguru import logger
from .registry import SkillRegistry

class SkillInstaller:
    """Installs dependencies and registers code packages as dynamic skills."""
    def __init__(self, registry: SkillRegistry = None):
        self.registry = registry or SkillRegistry()
        
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
            
    def install_skill_from_source(self, name: str, code: str, version: str, description: str, dependencies: List[str] = []) -> bool:
        """Writes custom skill code into the local skills workspace and registers it."""
        success = self.install_dependencies(dependencies)
        if not success:
            return False
            
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # import os locally to prevent reference error
        import os
        skill_dir = os.path.join(base_dir, "skills", "dynamic", name)
        os.makedirs(skill_dir, exist_ok=True)
        
        entry_file = os.path.join(skill_dir, "main.py")
        try:
            with open(entry_file, "w", encoding="utf-8") as f:
                f.write(code)
            self.registry.register_skill(name, version, description, entry_file, dependencies)
            return True
        except Exception as e:
            logger.error(f"Error saving skill source code: {e}")
            return False
