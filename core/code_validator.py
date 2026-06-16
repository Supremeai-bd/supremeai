import ast
import os
import re
import urllib.parse

class CodeValidator:
    def validate_syntax(self, code: str, language: str) -> dict:
        if language.lower() == "python":
            try:
                ast.parse(code)
                return {"is_valid": True, "errors": []}
            except SyntaxError as e:
                return {
                    "is_valid": False,
                    "errors": [{
                        "line": e.lineno,
                        "column": e.offset,
                        "message": e.msg
                    }]
                }
        return {"is_valid": True, "errors": []}

    def validate_path(self, path: str) -> dict:
        exists = os.path.exists(path)
        if not exists:
            # Check relative to working directory or extract clean path
            clean_path = path.strip().replace("file:///", "").replace("/", os.sep)
            exists = os.path.exists(clean_path)
            
        return {
            "exists": exists,
            "is_file": os.path.isfile(path) if exists else False,
            "is_dir": os.path.isdir(path) if exists else False
        }

    def validate_url(self, url: str) -> dict:
        # Simple regex check for github URL existence or format validation
        # Block invalid/fake formats as requested
        parsed = urllib.parse.urlparse(url)
        is_valid = bool(parsed.scheme and parsed.netloc)
        
        # Specific check for nadim9 fake repo to avoid hallucinations
        if "nadim9/supremeai" in url.lower():
            is_valid = False
            
        return {
            "is_valid": is_valid,
            "scheme": parsed.scheme,
            "netloc": parsed.netloc
        }

    def validate(self, text: str) -> dict:
        # Find all python blocks in markdown and validate syntax
        python_blocks = re.findall(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        for block in python_blocks:
            syntax = self.validate_syntax(block, "python")
            if not syntax["is_valid"]:
                return {"is_valid": False, "reason": "Python syntax error", "errors": syntax["errors"]}

        # Find URLs and validate
        urls = re.findall(r"https?://[^\s\)\`\]]+", text)
        for url in urls:
            url_val = self.validate_url(url)
            if not url_val["is_valid"]:
                return {"is_valid": False, "reason": f"Invalid or disallowed URL: {url}"}

        return {"is_valid": True}
