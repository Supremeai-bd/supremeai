import os
import re
import sys
import subprocess
from typing import List
from loguru import logger
from .registry import SkillRegistry

_SKILL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class SecurityError(Exception):
    """Exception raised for security violations during skill installation."""

    pass


class SkillInstaller:
    """Installs dependencies and registers code packages as dynamic skills."""

    def __init__(self, registry: SkillRegistry = None, skills_dir: str = None):
        self.registry = registry or SkillRegistry()
        if skills_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.skills_dir = os.path.join(base_dir, "skills", "dynamic")
        else:
            self.skills_dir = skills_dir

    def _sanitize_skill_name(self, name: str) -> str:
        if not name or not isinstance(name, str):
            raise ValueError("Invalid skill name.")
        if not _SKILL_NAME_PATTERN.match(name):
            raise ValueError("Skill name contains invalid characters.")
        if ".." in name or name.startswith("/") or name.startswith("\\"):
            raise ValueError("Path traversal detected in skill name.")
        return name

    def _pre_write_security_scan(self, code: str) -> None:
        try:
            import ast

            tree = ast.parse(code, filename="<skill>")
        except SyntaxError as e:
            raise ValueError(f"Syntax error in skill code: {e}") from e

        banned_modules = {
            "os",
            "sys",
            "subprocess",
            "shutil",
            "socket",
            "pty",
            "importlib",
            "code",
            "runpy",
            "pickle",
            "marshal",
            "tempfile",
            "urllib",
            "http",
            "requests",
            "ctypes",
            "__builtins__",
        }
        banned_names = {
            "eval",
            "exec",
            "compile",
            "__import__",
            "getattr",
            "setattr",
            "delattr",
            "globals",
            "locals",
            "open",
            "input",
            "breakpoint",
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module]
                )
                for mod_name in modules:
                    if mod_name and mod_name.split(".")[0] in banned_modules:
                        raise SecurityError(
                            f"Banned import '{mod_name}' blocked in skill install."
                        )
            elif isinstance(node, ast.Attribute) and (
                node.attr.startswith("__") or node.attr in banned_names
            ):
                raise SecurityError(
                    f"Malicious attribute access '{node.attr}' blocked in skill install."
                )
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in banned_names
            ):
                raise SecurityError(
                    f"Call to banned function '{node.func.id}' blocked in skill install."
                )

    def install_dependencies(self, dependencies: List[str]) -> bool:
        """Executes pip to install missing libraries dynamically."""
        if not dependencies:
            return True

        logger.info(f"Dynamic Installer installing: {dependencies}")
        try:
            cmd = [sys.executable, "-m", "pip", "install"] + dependencies
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("Installation completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e.stderr}")
            return False

    def install_skill_from_source(
        self,
        name: str,
        code: str,
        version: str,
        description: str,
        dependencies: List[str] | None = None,
        uss: dict | None = None,
    ) -> bool:
        """Writes custom skill code into the local skills workspace and registers it.
        বাংলা মন্তব্য: মিউটেবল ডিফল্ট আর্গুমেন্ট (List[str] = []) পরিহার করে None সেন্টিনেল প্যাটার্ন ব্যবহার করা হলো।
        """
        import os
        actual_deps = list(dependencies) if dependencies is not None else []

        if uss:
            from skills.schema import UniversalSkillSchema

            try:
                UniversalSkillSchema(**uss)
            except Exception as e:
                logger.error(
                    f"USS validation failed before installing skill '{name}': {e}"
                )
                return False

        try:
            safe_name = self._sanitize_skill_name(name)
        except Exception as e:
            logger.error(f"Skill name validation failed: {e}")
            return False

        try:
            self._pre_write_security_scan(code)
        except Exception as e:
            logger.error(f"Security scan failed before writing skill '{name}': {e}")
            return False

        success = self.install_dependencies(actual_deps)
        if not success:
            return False

        skill_dir = os.path.join(self.skills_dir, safe_name)
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

            self.registry.register_skill(
                safe_name, version, description, entry_file, actual_deps, uss=uss
            )
            return True
        except Exception as e:
            logger.error(f"Error saving skill source code: {e}")
            return False
