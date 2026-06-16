from typing import Any, Dict, List, Optional

from loguru import logger


def safe_execute(code: str) -> Dict[str, Any]:
    try:
        local_vars: Dict[str, Any] = {}
        exec(code, {"__builtins__": {}}, local_vars) # type: ignore[arg-type]
        if "result" in local_vars:
            return {"success": True, "value": local_vars["result"]}
        return {"success": True, "value": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def verify_symbolic_math(expression: str, claimed_result: str) -> Dict[str, Any]:
    import re
    try:
        import sympy
        expr = sympy.sympify(expression)
        claimed = sympy.sympify(claimed_result)
        is_correct = sympy.simplify(expr - claimed) == 0
        if not is_correct:
            try:
                is_correct = abs(expr.evalf() - claimed.evalf()) < 1e-9
            except Exception:
                pass
        return {
            "is_verified": bool(is_correct),
            "expression_sympy": str(expr),
            "claimed_result": str(claimed),
            "method": "sympy_symbolic"
        }
    except Exception as e:
        try:
            clean_expr = re.sub(r"[^0-9\+\-\*\/\(\)\.\s]", "", expression)
            result = eval(clean_expr)
            claimed = float(claimed_result.strip())
            is_correct = abs(result - claimed) < 1e-9
            return {
                "is_verified": is_correct,
                "numerical_result": result,
                "claimed_result": claimed,
                "method": "numerical_fallback"
            }
        except Exception as inner_e:
            return {"is_verified": False, "error": f"Sympy error: {e}, Fallback error: {inner_e}"}


class Thought:
    def __init__(self, content: str, reasoning_depth: int = 0):
        self.content = content
        self.reasoning_depth = reasoning_depth

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "thought", "content": self.content, "reasoning_depth": self.reasoning_depth}


class ChainOfThoughtReasoner:
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
        self._sympy_available = self._check_sympy()

    def _check_sympy(self) -> bool:
        try:
            import sympy
            return True
        except ImportError:
            return False

    def verify(self, answer: str, expected: Optional[str] = None) -> Dict[str, Any]:
        if expected is not None:
            math_matches = __import__('re').findall(r"(\d+[\+\-\*\/\(\)\d\s]+?)\s*=\s*(\S+)", answer)
            for expr, claimed in math_matches:
                mv = verify_symbolic_math(expr, claimed)
                if not mv.get("is_verified"):
                    return {"matches": False, "math_error": mv}
            return {"matches": answer.strip().lower() == expected.strip().lower(), "symbolic_verification": "passed"}
        return {"answer": answer}

    def symbolic_verify(self, expression: str, claimed: str) -> Dict[str, Any]:
        return verify_symbolic_math(expression, claimed)

    def _verify_execution(self, thought_payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_code = thought_payload.get("exec_code") or ""
        if not raw_code:
            return {"verified": True, "reason": "no_exec"}
        return safe_execute(raw_code)

    def refine_loop(self, problem: str, context: Optional[str] = None, expected: Optional[str] = None) -> Dict[str, Any]:
        last_output: Dict[str, Any] = {"thoughts": [], "exec_results": []}
        for iteration in range(self.max_iterations):
            prompt = self.build_prompt(problem, context)
            logger.info(f"CoT iteration {iteration} initiated")
            last_output["iter"] = iteration
            last_output["prompt_used"] = prompt
            if "answer" in last_output:
                exec_result = self._verify_execution({"exec_code": str(last_output.get("answer"))})
                last_output["exec_results"].append(exec_result)
        return {
            "status": "ok",
            "iterations": self.max_iterations,
            "thoughts": last_output.get("thoughts", []),
            "final_answer": last_output.get("answer", ""),
            "last_output": last_output,
        }
