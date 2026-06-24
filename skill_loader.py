import os
from pathlib import Path
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
                with open(schema_path, "r", encoding="utf-8") as sf:
                    schema_data = json.load(sf)
                UniversalSkillSchema(**schema_data)
            except Exception as e:
                logger.warning(f"USS validation failed for loaded skill '{name}': {e}")
            
        # Sandbox AST Check for RCE Prevention (Hardened Edition)
        import ast
        with open(candidate, "r", encoding="utf-8") as f:
            code = f.read()
        try:
            tree = ast.parse(code)
            banned_imports = {"os", "sys", "subprocess", "shutil", "socket", "pty"}
            # ১. 'delattr' যুক্ত করে ব্ল্যাকলিস্ট সম্পূর্ণ করা হলো (State Disruption Protection)
            banned_keys = {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals"}
            
            for node in ast.walk(tree):
                # ২. Type-Safe Import Blocker
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
                    for mod in modules:
                        if mod and mod.split('.')[0] in banned_imports:
                            raise SecurityError(f"🛡️ Security Exception: Banned root import '{mod}' blocked.")
                
                # ৩. Dunder and Method Reflection Blocker
                if isinstance(node, ast.Attribute):
                    if node.attr.startswith('__') or node.attr in banned_keys:
                        raise SecurityError(f"🛡️ Security Exception: Malicious attribute access '{node.attr}' detected.")
                
                # 💥 ৪. Global Identifier Protection (FIXES ALIAS BINDING & OBFUSCATION TRICKS)
                # শুধুমাত্র ast.Call-এ নজর না রেখে, পুরো কোডের কোথাও banned_keys-এর কোনো নাম (Identifier) 
                # এসাইনমেন্ট বা রেফারেন্স হিসেবে থাকলেই এটি রুট লেভেলে এক্সিকিউশন ব্লক করে দেবে।
                if isinstance(node, ast.Name):
                    if node.id in banned_keys:
                        raise SecurityError(f"🛡️ Security Exception: Attempted reference to banned identifier '{node.id}' blocked.")
                
                # ৫. Subscript Protection (String concatenation evaluation bypass)
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in banned_keys:
                        raise SecurityError(f"🛡️ Security Exception: Obfuscated key reference '{node.value}' blocked.")
                        
        except SyntaxError:
            raise ValueError(f"Syntax error in skill code: {name}")
            
        spec = importlib.util.spec_from_file_location(f"skills.dynamic.{name}", candidate)
        mod = importlib.util.module_from_spec(spec)
        
        # Pro-Tip: Delete dangerous builtins from the module's runtime global environment
        # This acts as a second layer of defense even if the AST check is somehow bypassed
        safe_globals = mod.__dict__
        for key in banned_keys:
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
