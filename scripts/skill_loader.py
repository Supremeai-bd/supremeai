import ast
from pathlib import Path
import importlib.util
from typing import Dict, Any, List
from loguru import logger
import sys
root_path = str(Path(__file__).resolve().parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from core.skill_manager import SkillManager
from skills.installer import SkillInstaller
from skills.marketplace import SkillMarketplace

class SecurityError(Exception):
    """Custom exception raised for AST sandbox validation failures."""
    pass

class BulletproofASTSandbox(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.is_secure = True
        self.violation_reason = None

        # ব্ল্যাকলিস্টেড মডিউল, অ্যাট্রিবিউটস এবং অবজেক্ট প্যারামিটার্স
        self.banned_tokens = {
            "__class__", "__subclasses__", "__globals__", "__code__",
            "__import__", "__builtins__", "eval", "exec", "os", "sys",
            "subprocess", "importlib", "shutil", "socket"
        }

    def _flag_violation(self, node, reason):
        self.is_secure = False
        self.violation_reason = f"Line {node.lineno}: {reason}"
        logger.warning(f"AST Sandbox Violation in '{self.filename}'! Details: {self.violation_reason}")

    def visit_Name(self, node):
        if node.id in self.banned_tokens:
            self._flag_violation(node, f"Direct usage of banned name/function '{node.id}'")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr in self.banned_tokens:
            self._flag_violation(node, f"Dangerous attribute access attempt: '{node.attr}'")
        self.generic_visit(node)

    def visit_Constant(self, node):
        # Python 3.8+ কনস্ট্যান্ট নোড স্ক্যানিং (যা স্ট্রিং লিটারেল কাভার করে)
        if isinstance(node.value, str):
            import re
            # বাংলা মন্তব্য: word boundary split করে exact banned token checking
            words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', node.value.lower()))
            for banned in self.banned_tokens:
                if banned in words:
                    self._flag_violation(node, f"Obfuscation payload detected in string literal: '{node.value}'")
                    return
        self.generic_visit(node)

    def visit_Str(self, node):
        # legacy python version compatible scanning
        import re
        words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', node.s.lower()))
        for banned in self.banned_tokens:
            if banned in words:
                self._flag_violation(node, f"Obfuscated legacy payload detected in string: '{node.s}'")
                return
        self.generic_visit(node)

    def visit_Call(self, node):
        # ডাইনামিক কোড রান করার ফাংশন ডাইরেক্ট ব্লক করা
        if isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "__import__", "open"}:
                self._flag_violation(node, f"Prohibited dynamic call: '{node.func.id}'")
        self.generic_visit(node)

def secure_sandbox_ast_check(code_string: str, filename: str) -> bool:
    """
    Parses and audits a given Python code snippet before compilation or execution.
    Returns True if fully compliant with SupremeAI sandbox criteria, False otherwise.
    """
    try:
        parsed_tree = ast.parse(code_string)
    except SyntaxError as e:
        logger.error(f"Syntax error during sandboxed parsing sequence: {e}")
        return False

    validator = BulletproofASTSandbox(filename)
    validator.visit(parsed_tree)
    return validator.is_secure

class SkillLoader:
    # Centralize security configuration for clarity and reusability.
    BANNED_IMPORTS = {"os", "sys", "subprocess", "shutil", "socket", "pty", "importlib", "code", "runpy", "pickle", "marshal", "tempfile", "urllib", "http", "requests", "ctypes", "__builtins__"}
    BANNED_BUILTINS = {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "globals", "locals", "open", "input", "breakpoint"}

    """Dynamically discovers and loads skill modules at runtime."""
    def __init__(self, registry: SkillManager = None, installer: SkillInstaller = None):
        self.registry = registry or SkillManager()
        self.installer = installer or SkillInstaller(self.registry)
        self.marketplace = SkillMarketplace()
        self.skills_dir = Path(__file__).resolve().parent / "skills" / "dynamic"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: Dict[str, Any] = {}

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
                schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
                UniversalSkillSchema(**schema_data)
            except Exception as e:
                logger.warning(f"USS validation failed for loaded skill '{name}': {e}")

        code = candidate.read_text(encoding="utf-8")
        if not secure_sandbox_ast_check(code, str(candidate)):
            raise SecurityError(f"🛡️ AST Sandbox validation failed for skill '{name}'.")

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
            source_url=skill["download_url"],
            target_dir=str(self.skills_dir)
        )
        return ok
