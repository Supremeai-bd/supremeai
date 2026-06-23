import os
import importlib.util
from typing import Dict, Any, List
from loguru import logger
from skills.registry import SkillRegistry
from skills.installer import SkillInstaller
from skills.marketplace import SkillMarketplace

class SkillLoader:
    """Dynamically discovers and loads skill modules at runtime."""
    def __init__(self, registry: SkillRegistry = None, installer: SkillInstaller = None):
        self.registry = registry or SkillRegistry()
        self.installer = installer or SkillInstaller(self.registry)
        self.marketplace = SkillMarketplace()
        self._loaded: Dict[str, Any] = {}

    def discover_local(self, skills_dir: str = None) -> List[str]:
        if skills_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(base_dir, "skills", "dynamic")
        os.makedirs(skills_dir, exist_ok=True)
        found = []
        for entry in os.listdir(skills_dir):
            path = os.path.join(skills_dir, entry)
            if os.path.isdir(path):
                main_py = os.path.join(path, "main.py")
                if os.path.exists(main_py):
                    found.append(entry)
        return found

    def load(self, name: str) -> Any:
        if name in self._loaded:
            return self._loaded[name]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(base_dir, "skills", "dynamic", name, "main.py")
        if not os.path.exists(candidate):
            raise FileNotFoundError(f"Skill not found: {name}")
            
        # Sandbox AST Check for RCE Prevention
        import ast
        with open(candidate, "r", encoding="utf-8") as f:
            code = f.read()
        try:
            tree = ast.parse(code)
            banned_imports = {"os", "sys", "subprocess", "shutil", "socket", "pty"}
            banned_calls = {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr"}
            
            for node in ast.walk(tree):
                # 1. Type-Safe Import Blocker (Relative Import crash protection included)
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
                    for mod in modules:
                        if mod and mod.split('.')[0] in banned_imports:
                            raise SecurityError(f"🛡️ Security Exception: Banned root import '{mod}' blocked.")
                
                # 2. God-Tier Dunder and Reflection Blocker (__subclasses__, getattr bypass prevention)
                if isinstance(node, ast.Attribute):
                    if node.attr.startswith('__') or node.attr in banned_calls:
                        raise SecurityError(f"🛡️ Security Exception: Malicious attribute access '{node.attr}' detected.")
                
                # 3. Strict Runtime Call Validator
                if isinstance(node, ast.Call):
                    # Direct call check (e.g. eval())
                    if isinstance(node.func, ast.Name) and node.func.id in banned_calls:
                        raise SecurityError(f"🛡️ Security Exception: Execution of compiler built-in '{node.func.id}' is strictly prohibited.")
                    # Object method call check (e.g. obj.getattr())
                    elif isinstance(node.func, ast.Attribute) and node.func.attr in banned_calls:
                        raise SecurityError(f"🛡️ Security Exception: Method level bypass wrapper '{node.func.attr}' blocked.")
                        
        except SyntaxError:
            raise ValueError(f"Syntax error in skill code: {name}")
            
        spec = importlib.util.spec_from_file_location(f"skills.dynamic.{name}", candidate)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._loaded[name] = mod
        return mod

    def search_and_install(self, query: str) -> bool:
        results = self.marketplace.search_skills(query)
        if not results:
            logger.info(f"No marketplace skills found for query '{query}'")
            return False
        skill = results[0]
        ok = self.installer.install_skill_from_source(
            name=skill["name"],
            code=skill.get("code", ""),
            version=skill.get("version", "1.0.0"),
            description=skill.get("description", ""),
            dependencies=skill.get("dependencies", []),
        )
        logger.info(f"Skill install for '{skill['name']}': {'ok' if ok else 'failed'}")
        return ok
