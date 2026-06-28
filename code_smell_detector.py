"""
CodeSmellDetector Agent

This agent scans the codebase for "code smells" like high cyclomatic complexity,
long methods, and large classes. It uses an AI model to automatically refactor
the problematic code into a simpler, more maintainable version.

Usage:
    python -m code_smell_detector <path_to_scan> --apply-changes

Dependencies:
    - google-generativeai (or your preferred LLM library)
"""
import os
import argparse
import ast
from typing import List, Dict, Any, Optional
from loguru import logger
import importlib.util


class CodeSmellDetector:
    """
    An agent that detects and refactors code with high cyclomatic complexity.
    """

    def __init__(self, thresholds: Optional[Dict[str, int]] = None):
        self.thresholds = thresholds or {
            "complexity": 10,
            "lines": 75,
            "args": 5,
            "class_methods": 15,
        }
        # সাধারণ স্ট্রিং যা ম্যাজিক স্ট্রিং হিসেবে গণ্য হবে না
        self.COMMON_STRINGS_TO_IGNORE = {
            '', 'utf-8', 'rb', 'wb', 'r', 'w', 'a', 'x', 'b', 't', '+'
        }
        logger.info(f"CodeSmellDetector initialized with thresholds: {self.thresholds}")

    async def _get_llm_refactor(self, code_block: str, smell_type: str, details: str) -> Optional[str]:
        """
        Uses an AI model to refactor a complex code block.
        """
        try:
            # Dynamically import ModelRouter to avoid circular dependencies if this file is moved
            spec = importlib.util.spec_from_file_location("model_router", "backend/brain/model_router.py")
            model_router_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(model_router_module)
            from brain.model_router import ModelRouter  # Assumes ModelRouter is available
            router = ModelRouter()
            prompt = (
                "You are an expert Python software engineer specializing in code refactoring.\n"
                "The following code block has a '{smell_type}' code smell: {details}.\n"
                "Refactor it to be simpler, more readable, and more maintainable while preserving its functionality.\n"
                "Only return the refactored Python code, without any explanation or markdown formatting.\n\n"
                "Original Code:\n```python\n{code}\n```\n\n"
                "Refactored Code:"
            ).format(smell_type=smell_type, details=details, code=code_block)

            response = await router.async_route_and_generate(prompt, task_type="coding")
            refactored_code = response.get("text", "").strip()

            # Clean up the response to get only the code
            if refactored_code.startswith("```python"):
                refactored_code = refactored_code[len("```python"):].strip()
            if refactored_code.endswith("```"):
                refactored_code = refactored_code[:-len("```")].strip()

            return refactored_code
        except Exception as e:
            logger.error(f"LLM refactoring failed: {e}")
            return None

    def _get_node_code(self, file_path: str, node: ast.AST) -> str:
        """
        Extracts a function/method/class's code from a file.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # ast nodes are 1-indexed for line numbers
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', start_line)
        
        return "".join(lines[start_line:end_line])

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculates cyclomatic complexity for a given AST node."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.ExceptHandler, ast.With, ast.Assert)):
                complexity += 1
        return complexity

    def _normalize_code_dump(self, dump: str) -> str:
        """Normalizes an AST dump to compare function bodies."""
        import re
        dump = re.sub(r"'(.*?)'", "''", dump)  # Normalize strings
        return re.sub(r'\s+', '', dump)

    def find_smelly_code(self, path: str) -> List[Dict[str, Any]]:
        """
        Scans a directory for Python files and finds code smells.
        """
        smelly_code = []
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    smelly_code.extend(self._analyze_file(file_path))
        return smelly_code

    def _analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Analyzes a single Python file for various code smells."""
        smells = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
            
            smells.extend(self._detect_duplicate_functions(tree, file_path))
            smells.extend(self._detect_magic_values(tree, file_path))

            for node in ast.walk(tree):
                details = ""
                smell_type = ""
                
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check for long method
                    complexity = self._calculate_complexity(node)
                    if complexity > self.thresholds["complexity"]:
                        smell_type = "High Cyclomatic Complexity"
                        details = f"Method '{node.name}' has a cyclomatic complexity of {complexity} (>{self.thresholds['complexity']})."


                    # Check for long method
                    num_lines = getattr(node, 'end_lineno', node.lineno) - node.lineno
                    if num_lines > self.thresholds["lines"]:
                        smell_type = "Long Method"
                        details = f"Method '{node.name}' has {num_lines} lines (>{self.thresholds['lines']})."

                    # Check for too many arguments
                    num_args = len(node.args.args)
                    if num_args > self.thresholds["args"]:
                        smell_type = "Too Many Arguments"
                        details = f"Method '{node.name}' has {num_args} arguments (>{self.thresholds['args']})."

                elif isinstance(node, ast.ClassDef):
                    # Check for large class
                    num_methods = sum(1 for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)))
                    if num_methods > self.thresholds["class_methods"]:
                        smell_type = "Large Class"
                        details = f"Class '{node.name}' has {num_methods} methods (>{self.thresholds['class_methods']})."

                if smell_type and details:
                    logger.warning(f"{smell_type} in {file_path}: {details}")
                    smells.append({
                        "file_path": file_path,
                        "smell_type": smell_type,
                        "details": details,
                        "original_code": self._get_node_code(file_path, node),
                    })
        except Exception as e:
            logger.error(f"Could not analyze {file_path}: {e}")
        return smells

    def _detect_magic_values(self, tree: ast.AST, file_path: str) -> List[Dict[str, Any]]:
        """Detects 'magic' strings and numbers that should be constants."""
        smells: List[Dict[str, Any]] = []

        for node in ast.walk(tree):
            # We are looking for ast.Constant which holds literals like strings, numbers, bools.
            if isinstance(node, ast.Constant):
                smell_type = ""
                details = ""

                # Check for magic strings
                if isinstance(node.value, str) and len(node.value) > 3 and node.value not in self.COMMON_STRINGS_TO_IGNORE:
                    # Avoid detecting strings in assignments that look like constants
                    parent = getattr(node, 'parent', None)
                    if parent and isinstance(parent, ast.Assign):
                        for target in parent.targets:
                            if isinstance(target, ast.Name) and target.id.isupper():
                                continue # This is likely a constant definition, so skip

                    smell_type = "Magic String"
                    details = f"Hardcoded string '{node.value}' found. Consider defining it as a constant."

                # Check for magic numbers (that are not 0 or 1)
                elif isinstance(node.value, (int, float)) and node.value not in {0, 1}:
                    smell_type = "Magic Number"
                    details = f"Hardcoded number '{node.value}' found. Consider defining it as a named constant."

                if smell_type:
                    smells.append({
                        "file_path": file_path,
                        "smell_type": smell_type,
                        "details": details,
                        "original_code": f"'{node.value}'" if isinstance(node.value, str) else str(node.value),
                    })
        return smells

    def _detect_duplicate_functions(self, tree: ast.AST, file_path: str) -> List[Dict[str, Any]]:
        """Detects duplicate function bodies within a file."""
        smells: List[Dict[str, Any]] = []
        function_bodies: Dict[str, List[Dict[str, Any]]] = {}

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Exclude simple one-liners like `pass` or `return`
                if len(node.body) == 1 and isinstance(node.body[0], (ast.Pass, ast.Return)):
                    continue
                
                body_dump = self._normalize_code_dump(ast.dump(node.body))
                
                if body_dump not in function_bodies:
                    function_bodies[body_dump] = []
                
                function_bodies[body_dump].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "original_code": self._get_node_code(file_path, node)
                })

        for body_dump, nodes in function_bodies.items():
            if len(nodes) > 1:
                locations = ", ".join([f"'{n['name']}' (line {n['lineno']})" for n in nodes])
                for node_info in nodes:
                    smells.append({
                        "file_path": file_path,
                        "smell_type": "Duplicate Code",
                        "details": f"Duplicate function body found for '{node_info['name']}'. Similar logic in: {locations}.",
                        "original_code": node_info['original_code'],
                    })
        return smells


    async def refactor_and_apply(self, file_path: str, original_code: str, refactored_code: str):
        """
        Replaces the original complex code with the AI-refactored version in the file.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = content.replace(original_code, refactored_code)

        if new_content == content:
            logger.error(f"Failed to apply refactoring for {file_path}. Code block not found.")
            return

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        logger.success(f"Successfully applied refactoring to {file_path}")



async def main():
    parser = argparse.ArgumentParser(description="Detect and refactor complex code.")
    parser.add_argument("path", help="Path to scan for Python files.")
    parser.add_argument("--max-complexity", type=int, default=10, help="Maximum cyclomatic complexity allowed.")
    parser.add_argument("--apply-changes", action="store_true", help="Apply refactorings directly to files.")
    args = parser.parse_args()
    
    thresholds = {
        "complexity": args.max_complexity,
        "lines": 60,
        "args": 6,
        "class_methods": 20,
    }
    detector = CodeSmellDetector(thresholds=thresholds)
    smelly_code_blocks = detector.find_smelly_code(args.path)
    
    for block in smelly_code_blocks:
        refactored = await detector._get_llm_refactor(block["original_code"], block["smell_type"], block["details"])
        if refactored and args.apply_changes:
            await detector.refactor_and_apply(block["file_path"], block["original_code"], refactored)
        elif refactored:
            logger.info(f"Suggested refactoring for {block['file_path']}:\n{refactored}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())