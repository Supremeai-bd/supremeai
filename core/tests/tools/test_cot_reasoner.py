import ast
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.code.cot_reasoner import (
    ChainOfThoughtReasoner,
    DeepReasoningChain,
    Thought,
    _eval_node,
    _safe_eval_math,
    verify_symbolic_math,
)


class FakeSympy:
    """Lightweight stand-in for sympy used in tests."""

    class Expr:
        __hash__ = None

        def __sub__(self, other):
            return 0

        def __eq__(self, other):
            return other == 0

        def evalf(self):
            return 0.0

    @staticmethod
    def sympify(expr):
        return FakeSympy.Expr()

    @staticmethod
    def simplify(expr):
        return 0

    @staticmethod
    def evalf():
        return 0.0


def _patch_sympy_in_modules():
    return patch.dict(sys.modules, {"sympy": FakeSympy()})


# ---------------------------------------------------------------------------
# _eval_node
# ---------------------------------------------------------------------------


class TestEvalNode:
    def test_binary_add(self):
        node = ast.parse("2 + 3", mode="eval").body
        assert _eval_node(node) == 5

    def test_binary_subtract(self):
        node = ast.parse("10 - 4", mode="eval").body
        assert _eval_node(node) == 6

    def test_binary_multiply(self):
        node = ast.parse("3 * 7", mode="eval").body
        assert _eval_node(node) == 21

    def test_binary_divide(self):
        node = ast.parse("10 / 4", mode="eval").body
        assert _eval_node(node) == 2.5

    def test_binary_floor_divide(self):
        node = ast.parse("7 // 2", mode="eval").body
        assert _eval_node(node) == 3

    def test_binary_modulo(self):
        node = ast.parse("7 % 2", mode="eval").body
        assert _eval_node(node) == 1

    def test_binary_power(self):
        node = ast.parse("2 ** 3", mode="eval").body
        assert _eval_node(node) == 8

    def test_unary_negation(self):
        node = ast.parse("-3", mode="eval").body
        assert _eval_node(node) == -3

    def test_unary_positive(self):
        node = ast.parse("+5", mode="eval").body
        assert _eval_node(node) == 5

    def test_float_constant(self):
        node = ast.parse("3.14", mode="eval").body
        assert _eval_node(node) == 3.14

    def test_negative_float_constant(self):
        node = ast.parse("-0.5", mode="eval").body
        assert _eval_node(node) == -0.5

    def test_complex_expression(self):
        node = ast.parse("2 * (3 + 4)", mode="eval").body
        assert _eval_node(node) == 14

    def test_unsupported_operator_raises(self):
        node = ast.parse("1 & 2", mode="eval").body

        with patch.dict("backend.tools.code.cot_reasoner._ALLOWED_OPERATORS", {}):
            with pytest.raises(ValueError, match="Unsupported operator"):
                _eval_node(node)

    def test_non_numeric_constant_raises(self):
        tree = ast.parse('"hello"', mode="eval")
        with pytest.raises(ValueError, match="Only numeric constants"):
            _eval_node(tree.body)

    def test_unsupported_node_raises(self):
        class UnsupportedNode:
            pass

        node = UnsupportedNode()
        with pytest.raises(ValueError, match="Unsupported expression node"):
            _eval_node(node)


# ---------------------------------------------------------------------------
# _safe_eval_math
# ---------------------------------------------------------------------------


class TestSafeEvalMath:
    def test_simple_add(self):
        assert _safe_eval_math("2 + 3") == 5

    def test_float_result(self):
        assert _safe_eval_math("10 / 4") == 2.5

    def test_complex_expression(self):
        assert _safe_eval_math("2 * (3 + 4)") == 14

    def test_power(self):
        assert _safe_eval_math("2 ** 10") == 1024

    def test_invalid_expression_raises(self):
        with pytest.raises((SyntaxError, ValueError)):
            _safe_eval_math("import os")


# ---------------------------------------------------------------------------
# verify_symbolic_math
# ---------------------------------------------------------------------------


class TestVerifySymbolicMath:
    def test_sympy_success_returns_verified(self):
        with _patch_sympy_in_modules():
            result = verify_symbolic_math("x + x", "2*x")
        assert result["is_verified"] is True
        assert result["method"] == "sympy_symbolic"

    def test_sympy_success_preserves_keys(self):
        with _patch_sympy_in_modules():
            result = verify_symbolic_math("x**2", "x * x")
        assert "expression_sympy" in result
        assert "claimed_result" in result
        assert result["method"] == "sympy_symbolic"

    def test_sympy_fails_falls_back_to_numerical(self):
        class FakeSympyRaise:
            @staticmethod
            def sympify(x):
                raise RuntimeError("bad")

        with patch.dict("sys.modules", {"sympy": FakeSympyRaise()}):
            result = verify_symbolic_math("2 + 2", "4")
        assert result["is_verified"] is True
        assert result["method"] == "numerical_fallback"

    def test_numerical_failure_returns_error(self):
        class FakeSympyRaise:
            @staticmethod
            def sympify(x):
                raise RuntimeError("bad")

        with (
            patch.dict("sys.modules", {"sympy": FakeSympyRaise()}),
            patch(
                "backend.tools.code.cot_reasoner._safe_eval_math",
                side_effect=ValueError("bad"),
            ),
        ):
            result = verify_symbolic_math("???", "???")
        assert result["is_verified"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# Thought
# ---------------------------------------------------------------------------


class TestThought:
    def test_add_child_increments_depth(self):
        root = Thought("root")
        child = root.add_child("child")
        assert child.reasoning_depth == 1
        assert child.parent is root

    def test_add_child_multiple_children(self):
        root = Thought("root")
        c1 = root.add_child("first")
        c2 = root.add_child("second")
        assert len(root.children) == 2
        assert c1.parent is root
        assert c2.parent is root

    def test_add_child_default_score(self):
        root = Thought("root")
        child = root.add_child("scored")
        assert child.score == 0.0

    def test_to_dict_leaf(self):
        t = Thought("hello", reasoning_depth=2, score=0.9)
        d = t.to_dict()
        assert d["type"] == "thought"
        assert d["content"] == "hello"
        assert d["reasoning_depth"] == 2
        assert d["score"] == 0.9
        assert d["children"] == []

    def test_to_dict_nested(self):
        root = Thought("root", score=0.5)
        child = root.add_child("child", score=0.7)
        child.add_child("grandchild", score=0.8)
        d = root.to_dict()
        assert len(d["children"]) == 1
        assert d["children"][0]["content"] == "child"
        assert d["children"][0]["children"][0]["content"] == "grandchild"


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_without_context(self):
        r = ChainOfThoughtReasoner()
        p = r.build_prompt("What is 2+2?")
        assert "What is 2+2?" in p
        assert "<thought>" in p
        assert "<answer>" in p

    def test_with_context(self):
        r = ChainOfThoughtReasoner()
        p = r.build_prompt("What is 2+2?", context="Check carefully")
        assert "What is 2+2?" in p
        assert "Context: Check carefully" in p

    def test_always_ends_with_begin(self):
        r = ChainOfThoughtReasoner()
        p = r.build_prompt("X")
        assert p.endswith("Begin your thought process now:")


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.parse
# ---------------------------------------------------------------------------


class TestParse:
    def test_basic_parse(self):
        r = ChainOfThoughtReasoner()
        raw = "<thought>First step</thought><answer>42</answer>"
        out = r.parse(raw)
        assert len(out["thoughts"]) == 1
        assert out["thoughts"][0]["content"] == "First step"
        assert out["final_answer"] == "42"
        assert out["raw"] == raw

    def test_multiple_thoughts(self):
        r = ChainOfThoughtReasoner()
        raw = "<thought>A</thought><thought>B</thought><answer>X</answer>"
        out = r.parse(raw)
        assert len(out["thoughts"]) == 2
        assert out["thoughts"][0]["content"] == "A"
        assert out["thoughts"][1]["content"] == "B"

    def test_no_thoughts(self):
        r = ChainOfThoughtReasoner()
        out = r.parse("<answer>only answer</answer>")
        assert len(out["thoughts"]) == 0
        assert out["final_answer"] == "only answer"

    def test_no_answer(self):
        r = ChainOfThoughtReasoner()
        out = r.parse("<thought>thinking</thought>")
        assert out["final_answer"] == ""

    def test_case_insensitive_tags(self):
        r = ChainOfThoughtReasoner()
        raw = "<Thought>Step</Thought><Answer>ans</Answer>"
        out = r.parse(raw)
        assert len(out["thoughts"]) == 1
        assert out["final_answer"] == "ans"

    def test_dotall_multiline_thoughts(self):
        r = ChainOfThoughtReasoner()
        raw = "<thought>line1\nline2</thought><answer>x</answer>"
        out = r.parse(raw)
        assert out["thoughts"][0]["content"] == "line1\nline2"


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.evaluate_thought
# ---------------------------------------------------------------------------


class TestEvaluateThought:
    def test_base_score(self):
        r = ChainOfThoughtReasoner()
        t = Thought("random words")
        assert r.evaluate_thought(t) == pytest.approx(0.5)

    def test_conclusion_keyword_boost(self):
        r = ChainOfThoughtReasoner()
        t = Thought("therefore the answer is clear")
        assert r.evaluate_thought(t) >= 0.7

    def test_contrast_keyword_boost(self):
        r = ChainOfThoughtReasoner()
        t = Thought("however we must check")
        assert r.evaluate_thought(t) >= 0.6

    def test_length_boost(self):
        r = ChainOfThoughtReasoner()
        words = " ".join(["w"] * 10)
        t = Thought(words)
        assert r.evaluate_thought(t) >= 0.6

    def test_context_keyword_boost(self):
        r = ChainOfThoughtReasoner()
        t = Thought("math is fun")
        score = r.evaluate_thought(t, context="math matters")
        assert score >= 0.6

    def test_score_clamped_to_one(self):
        r = ChainOfThoughtReasoner()
        t = Thought(
            "therefore thus conclusion final answer however although alternatively "
            + " ".join(["x"] * 20)
        )
        score = r.evaluate_thought(t, context="thus")
        assert score <= 1.0

    def test_none_context(self):
        r = ChainOfThoughtReasoner()
        t = Thought("short")
        score = r.evaluate_thought(t, context=None)
        assert score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.tree_search
# ---------------------------------------------------------------------------


class TestTreeSearch:
    def test_depth_zero_returns_early(self):
        r = ChainOfThoughtReasoner()
        out = r.tree_search("problem", branches=3, depth=0)
        assert out["status"] == "ok"
        assert out["best_branch"] == []
        assert out["best_score"] == 0.0

    def test_zero_branches_returns_early(self):
        r = ChainOfThoughtReasoner()
        out = r.tree_search("problem", branches=0, depth=2)
        assert out["best_branch"] == []
        assert out["best_score"] == 0.0

    def test_empty_parse_returns_early(self, monkeypatch):
        r = ChainOfThoughtReasoner()
        monkeypatch.setattr(
            r, "parse", lambda raw: {"thoughts": [], "final_answer": "", "raw": raw}
        )
        out = r.tree_search("problem")
        assert out["best_branch"] == []
        assert out["best_score"] == 0.0

    def test_tracks_best_branch_score(self, monkeypatch):
        r = ChainOfThoughtReasoner()

        def fake_parse(raw):
            return {
                "thoughts": [{"content": "thought1", "reasoning_depth": 0, "score": 0.3}],
                "final_answer": "",
                "raw": raw,
            }

        monkeypatch.setattr(r, "parse", fake_parse)
        monkeypatch.setattr(
            r,
            "evaluate_thought",
            lambda thought, context=None: 0.9,
        )
        out = r.tree_search("problem", branches=3, depth=1)
        assert out["best_score"] == 0.9
        assert "thought1" in out["best_branch"]

    def test_extended_depth_creates_child(self, monkeypatch):
        r = ChainOfThoughtReasoner()

        def fake_parse(raw):
            if "Continue" not in raw:
                return {
                    "thoughts": [{"content": "thought1", "reasoning_depth": 0, "score": 0.3}],
                    "final_answer": "",
                    "raw": raw,
                }
            return {
                "thoughts": [{"content": "thought1 - continued", "reasoning_depth": 1}],
                "final_answer": "",
                "raw": raw,
            }

        monkeypatch.setattr(r, "parse", fake_parse)
        monkeypatch.setattr(
            r,
            "evaluate_thought",
            lambda thought, context=None: 0.6,
        )
        out = r.tree_search("problem", branches=3, depth=2)
        assert out["status"] == "ok"
        assert out["best_branch"] is not None


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner._verify_execution
# ---------------------------------------------------------------------------


class TestVerifyExecution:
    def test_no_code_returns_no_exec(self):
        r = ChainOfThoughtReasoner()
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"tools.safe_executor": fake_module}, clear=False):
            result = r._verify_execution({})
        assert result["verified"] is True
        assert result["reason"] == "no_exec"

    def test_executes_code(self):
        r = ChainOfThoughtReasoner()
        fake_module = MagicMock()
        fake_module.run_restricted = MagicMock(return_value={"result": 42})
        # বাংলা মন্তব্য: মডিউল রিলোকেশন অনুযায়ী মক পাথ tools.code.safe_executor করা হলো।
        with patch.dict("sys.modules", {"tools.code.safe_executor": fake_module}, clear=False):
            result = r._verify_execution({"exec_code": "x = 1"})
        assert result["success"] is True


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_verify_math_mismatch(self):
        r = ChainOfThoughtReasoner()
        answer = "2 + 2 = 5"
        result = r.verify(answer, expected="4")
        assert result.get("matches") is False
        assert "math_error" in result

    def test_verify_exact_match(self):
        r = ChainOfThoughtReasoner()
        result = r.verify("hello", expected="hello")
        assert result["matches"] is True

    def test_verify_case_insensitive_match(self):
        r = ChainOfThoughtReasoner()
        result = r.verify("HELLO", expected="hello")
        assert result["matches"] is True

    def test_verify_without_expected(self):
        r = ChainOfThoughtReasoner()
        result = r.verify("anything")
        assert result == {"answer": "anything"}


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.symbolic_verify
# ---------------------------------------------------------------------------


class TestSymbolicVerify:
    def test_delegates_to_verify_symbolic_math(self):
        r = ChainOfThoughtReasoner()
        with _patch_sympy_in_modules():
            result = r.symbolic_verify("x**2", "x * x")
        assert result["is_verified"] is True


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner.refine_loop
# ---------------------------------------------------------------------------


class TestRefineLoop:
    def test_returns_ok_status(self):
        r = ChainOfThoughtReasoner(max_iterations=2)
        result = r.refine_loop("solve x")
        assert result["status"] == "ok"
        assert result["iterations"] == 2

    def test_logs_each_iteration(self):
        r = ChainOfThoughtReasoner(max_iterations=3)
        result = r.refine_loop("solve x")
        assert result["iterations"] == 3


# ---------------------------------------------------------------------------
# DeepReasoningChain
# ---------------------------------------------------------------------------


class TestDeepReasoningChain:
    def test_multi_step_think_prompt(self):
        chain = DeepReasoningChain()
        result = chain.multi_step_think("Solve x=1")
        assert "Step 1:" in result
        assert "Solve x=1" in result
        assert "Final Answer:" in result

    def test_self_critique_prompt(self):
        chain = DeepReasoningChain()
        solution = "The answer is 42."
        result = chain.self_critique(solution)
        assert "Review the following solution" in result
        assert solution in result

    def test_iterative_refinement_iterates(self):
        chain = DeepReasoningChain(max_iterations=3)
        answer = "draft answer"
        result = chain.iterative_refinement(answer, iterations=2)
        assert "draft answer" in result
        assert "Critique:" in result


# ---------------------------------------------------------------------------
# ChainOfThoughtReasoner._check_sympy
# ---------------------------------------------------------------------------


class TestCheckSympy:
    def test_sympy_availability_flag(self):
        r = ChainOfThoughtReasoner()
        assert hasattr(r, "_sympy_available")
        assert isinstance(r._sympy_available, bool)
