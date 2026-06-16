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


class Thought:
    def __init__(self, content: str, reasoning_depth: int = 0):
        self.content = content
        self.reasoning_depth = reasoning_depth

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "thought", "content": self.content, "reasoning_depth": self.reasoning_depth}


class ChainOfThoughtReasoner:
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations

    def build_prompt(self, problem: str, context: Optional[str] = None) -> str:
        parts = [
            "You are a step-by-step reasoning engine. Carefully analyze the problem solving steps.",
            "For each step, wrap your chain-of-thought inside <thought>...</thought> tags.",
            "After finishing thinking, return the final answer only inside <answer>...</answer> tags with no extra explanation.",
            "",
            f"Problem: {problem}",
        ]
        if context:
            parts.extend(["", f"Context: {context}"])
        parts.extend(["", "Begin your thought process now:"])
        return "\n".join(parts)

    def parse(self, raw: str) -> Dict[str, Any]:
        thoughts: List[str] = []
        answer = ""
        import re
        for tag in re.findall(r"<thought>(.*?)</thought>", raw, flags=re.DOTALL | re.IGNORECASE):
            thoughts.append(tag.strip())
        answer_match = re.search(r"<answer>(.*?)</answer>", raw, flags=re.DOTALL | re.IGNORECASE)
        if answer_match:
            answer = answer_match.group(1).strip()
        return {
            "thoughts": [Thought(t, idx).to_dict() for idx, t in enumerate(thoughts)],
            "final_answer": answer,
            "raw": raw,
        }

    def verify(self, answer: str, expected: Optional[str] = None) -> Dict[str, Any]:
        if expected is not None:
            return {"matches": answer.strip().lower() == expected.strip().lower()}
        return {"answer": answer}

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
