import os
from pathlib import Path
import importlib.util
from typing import Dict, Any, List
from loguru import logger
from skills.registry import SkillRegistry
from skills.installer import SkillInstaller
from skills.marketplace import SkillMarketplace

class SkillLoader:
    # Centralize security configuration for clarity and reusability.
    BANNED_IMPORTS = {"os", "sys", "subprocess", "shutil", "socket", "pty"}
    # Added 'open' to prevent arbitrary file I/O.
    BANNED_BUILTINS = {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals", "open"}

    """Dynamically discovers and loads skill modules at runtime."""
    def __init__(self, registry: SkillRegistry = None, installer: SkillInstaller = None):
        self.registry = registry or SkillRegistry()
        self.installer = installer or SkillInstaller(self.registry)
        self.marketplace = SkillMarketplace()
        self._loaded: Dict[str, Any] = {}
        # মাত্র এক লাইনে গ্লোবাল পাথ ডিক্লেয়ারেশন
        self.skills_dir = Path(__file__).resolve().parent / "skills" / "dynamic"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def discover_local(self) -> List[str]:
        found = []
        if self.skills_dir.exists():
            for entry in self.skills_dir.iterdir():
                if entry.is_dir() and (entry / "main.py").exists():
                    found.append(entry.name)
        return found

    def _sandbox_ast_check(self, code: str, filename: str):
        """
        Performs AST-based security checks to prevent RCE and other malicious activities.
        Raises SecurityError if a banned pattern is detected.
        """
        import ast
        try:
            tree = ast.parse(code, filename=filename)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in skill code: {filename}") from e

        for node in ast.walk(tree):
            # 1. Import Blocker: Prevents importing dangerous modules.
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
                for mod_name in modules:
                    if mod_name and mod_name.split('.')[0] in self.BANNED_IMPORTS:
                        raise SecurityError(f"🛡️ Banned import '{mod_name}' blocked in skill '{filename}'.")

            # 2. Attribute Access Blocker: Prevents access to dunder methods and sensitive attributes.
            elif isinstance(node, ast.Attribute) and (node.attr.startswith('__') or node.attr in self.BANNED_BUILTINS):
                raise SecurityError(f"🛡️ Malicious attribute access '{node.attr}' blocked in skill '{filename}'.")

            # 3. Function Call Blocker: Prevents direct calls to banned built-in functions.
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.BANNED_BUILTINS:
                raise SecurityError(f"🛡️ Call to banned function '{node.func.id}' blocked in skill '{filename}'.")

    def load(self, name: str) -> Any:
        if name in self._loaded:
            return self._loaded[name]

        candidate = self.skills_dir / name / "main.py"
        if not candidate.exists():
            raise FileNotFoundError(f"Skill not found: {name}")

        schema_path = self.skills_dir / name / "schema.json"
        if schema_path.exists():
            import json
            from skills.schema import UniversalSkillSchema
            try:
                schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
                UniversalSkillSchema(**schema_data)
            except Exception as e:
                logger.warning(f"USS validation failed for loaded skill '{name}': {e}")

        code = candidate.read_text(encoding="utf-8")
        self._sandbox_ast_check(code, str(candidate))

        spec = importlib.util.spec_from_file_location(f"skills.dynamic.{name}", candidate)
        mod = importlib.util.module_from_spec(spec)
        
        # Pro-Tip: Delete dangerous builtins from the module's runtime global environment
        # This acts as a second layer of defense even if the AST check is somehow bypassed
        safe_globals = mod.__dict__
        for key in self.BANNED_BUILTINS:
            if 'builtins' in safe_globals:
                b_dict = safe_globals['builtins'].__dict__ if hasattr(safe_globals['builtins'], '__dict__') else safe_globals['builtins']
                if isinstance(b_dict, dict) and key in b_dict:
                    del b_dict[key]
            if '__builtins__' in safe_globals:
                b_dict = safe_globals['__builtins__'].__dict__ if hasattr(safe_globals['__builtins__'], '__dict__') else safe_globals['__builtins__']
                if isinstance(b_dict, dict) and key in b_dict:
                    del b_dict[key]
                    
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
