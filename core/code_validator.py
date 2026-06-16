import ast
import os
import re
import urllib.parse
import sys

class AICodeValidator:
    def validate_before_use(self, ai_generated_code: str) -> dict:
        checks = {
            'syntax_valid': self._check_syntax(ai_generated_code),
            'indentation_correct': self._check_indentation(ai_generated_code),
            'no_hallucinated_imports': self._check_imports_exist(ai_generated_code),
            'no_undefined_variables': self._check_variables_defined(ai_generated_code),
            'no_infinite_loops': self._check_loop_safety(ai_generated_code),
        }
        all_passed = all(checks.values())
        return {
            'can_use': all_passed,
            'checks': checks,
            'fixed_code': self._auto_fix(ai_generated_code) if not all_passed else ai_generated_code
        }

    def _check_syntax(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _check_indentation(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except IndentationError:
            return False
        except SyntaxError as e:
            if "unexpected indent" in str(e) or "unindent does not match" in str(e):
                return False
            return True

    def _check_imports_exist(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self._module_exists(alias.name):
                            return False
                elif isinstance(node, ast.ImportFrom):
                    if not self._module_exists(node.module):
                        return False
            return True
        except Exception:
            return False

    def _module_exists(self, module_name: str) -> bool:
        if not module_name:
            return False
        base_module = module_name.split('.')[0]
        # Ignore custom local modules that might not be in path
        if base_module in ["core", "brain", "interfaces", "skills"]:
            return True
        try:
            __import__(base_module)
            return True
        except ImportError:
            return False

    def _check_variables_defined(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            defined = set()
            used = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Store):
                        defined.add(node.id)
                    elif isinstance(node.ctx, ast.Load):
                        used.add(node.id)
                elif isinstance(node, ast.FunctionDef):
                    defined.add(node.name)
                    for arg in node.args.args:
                        defined.add(arg.arg)
                elif isinstance(node, ast.ClassDef):
                    defined.add(node.name)
            
            # Filter out builtins
            import builtins
            builtin_names = set(dir(builtins))
            undefined = used - defined - builtin_names
            return len(undefined) == 0
        except Exception:
            return False

    def _check_loop_safety(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.While, ast.For)):
                    # Check if there is a break or return or if condition is not always True
                    if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
                        has_break = False
                        for subnode in ast.walk(node):
                            if isinstance(subnode, (ast.Break, ast.Return)):
                                has_break = True
                                break
                        if not has_break:
                            return False
            return True
        except Exception:
            return False

    def _auto_fix(self, code: str) -> str:
        # Simple auto-fix placeholder or basic indent correction
        return code


class CodeValidator:
    def __init__(self):
        self.ai_validator = AICodeValidator()

    def validate_syntax(self, code: str, language: str) -> dict:
        if language.lower() == "python":
            res = self.ai_validator.validate_before_use(code)
            return {
                "is_valid": res["can_use"],
                "errors": [{"message": "AICodeValidator check failed", "checks": res["checks"]}] if not res["can_use"] else []
            }
        return {"is_valid": True, "errors": []}

    def validate_path(self, path: str) -> dict:
        exists = os.path.exists(path)
        if not exists:
            clean_path = path.strip().replace("file:///", "").replace("/", os.sep)
            exists = os.path.exists(clean_path)
            
        return {
            "exists": exists,
            "is_file": os.path.isfile(path) if exists else False,
            "is_dir": os.path.isdir(path) if exists else False
        }

    def validate_url(self, url: str) -> dict:
        parsed = urllib.parse.urlparse(url)
        is_valid = bool(parsed.scheme and parsed.netloc)
        
        if "nadim9/supremeai" in url.lower():
            is_valid = False
            
        return {
            "is_valid": is_valid,
            "scheme": parsed.scheme,
            "netloc": parsed.netloc
        }

    def validate(self, text: str) -> dict:
        python_blocks = re.findall(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        for block in python_blocks:
            syntax = self.validate_syntax(block, "python")
            if not syntax["is_valid"]:
                return {"is_valid": False, "reason": "Python syntax or validation error", "errors": syntax["errors"]}

        urls = re.findall(r"https?://[^\s\)\`\]]+", text)
        for url in urls:
            url_val = self.validate_url(url)
            if not url_val["is_valid"]:
                return {"is_valid": False, "reason": f"Invalid or disallowed URL: {url}"}

        return {"is_valid": True}

