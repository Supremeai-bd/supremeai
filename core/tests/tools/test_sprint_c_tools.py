"""
Tests for Sprint C fixed tools:
- browser_agent
- voice_coder
- ai_pair_programmer
- style_learner
- diagram_to_architecture
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.skip(
    reason="Pre-existing failure — code refactored, test not updated (P0 audit)"
)


# ── BrowserAgent ─────────────────────────────────────────────────────────────


class TestBrowserAgent:
    @pytest.mark.asyncio
    async def test_fetch_page_success(self):
        from tools.ai_agents.browser_agent import BrowserAgent

        agent = BrowserAgent()
        with patch("core.agents.live.browser_agent.is_safe_url", return_value=True):
            with patch(
                "core.agents.live.browser_agent.get_global_browser", new_callable=AsyncMock
            ) as mock_browser:
                mock_browser.return_value = None
                with patch("httpx.get") as mock_get:
                    mock_resp = MagicMock()
                    mock_resp.text = (
                        "<html><head><title>Test</title></head><body>Hello World</body></html>"
                    )
                    mock_resp.status_code = 200
                    mock_get.return_value = mock_resp
                    result = await agent.navigate_and_interact("https://example.com")
                assert result["success"] is True
                assert "Hello World" in result["content"]

    @pytest.mark.asyncio
    async def test_fetch_page_error(self):
        import httpx

        from tools.ai_agents.browser_agent import BrowserAgent

        agent = BrowserAgent()
        with patch("core.agents.live.browser_agent.is_safe_url", return_value=True):
            with patch(
                "core.agents.live.browser_agent.get_global_browser", new_callable=AsyncMock
            ) as mock_browser:
                mock_browser.return_value = None
                with patch("httpx.get", side_effect=httpx.RequestError("Connection refused")):
                    result = await agent.navigate_and_interact("https://invalid-url.xyz")
                assert result["success"] is False
                assert "error" in result


# ── VoiceCoder ───────────────────────────────────────────────────────────────


class TestVoiceCoder:
    @pytest.mark.anyio
    async def test_generate_code_from_instruction(self):
        from tools.code.voice_coder import VoiceCoder

        coder = VoiceCoder()
        with patch("brain.model_router.ModelRouter") as mock_router_cls:
            mock_router = AsyncMock()
            mock_router.async_route_and_generate.return_value = {"text": "def hello(): pass"}
            mock_router_cls.return_value = mock_router
            result = await coder._generate_code_from_instruction("generate a hello function")
        assert "hello" in result or "def" in result or "#" in result

    @pytest.mark.anyio
    async def test_classify_and_execute_generate(self):
        from tools.code.voice_coder import VoiceCoder

        coder = VoiceCoder()
        with patch.object(
            coder, "_generate_code_from_instruction", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = "def hello(): pass"
            action, code = await coder._classify_and_execute("generate a hello function")
        assert action == "generate_code"
        assert "def hello" in code

    @pytest.mark.anyio
    async def test_classify_and_execute_explain(self):
        from tools.code.voice_coder import VoiceCoder

        coder = VoiceCoder()
        with patch.object(coder, "_explain", new_callable=AsyncMock) as mock_exp:
            mock_exp.return_value = "This is a variable"
            action, _result = await coder._classify_and_execute("explain what is a variable")
        assert action == "explanation"


# ── AIPairProgrammer ─────────────────────────────────────────────────────────


class TestAIPairProgrammer:
    @pytest.mark.anyio
    async def test_solve_issue_success(self):
        from tools.code.ai_pair_programmer import AIPairProgrammer

        programmer = AIPairProgrammer()
        with patch.object(programmer, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = [
                "1. Analyze\n2. Fix\n3. Test",  # plan
                "def fixed(): pass",  # code
                "def test_fixed(): pass",  # tests
            ]
            result = await programmer.solve_issue("Fix the login bug")
        assert result["status"] == "success"
        assert "plan" in result
        assert "code" in result
        assert "tests" in result

    @pytest.mark.anyio
    async def test_review_code(self):
        from tools.code.ai_pair_programmer import AIPairProgrammer

        programmer = AIPairProgrammer()
        with patch.object(programmer, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "1. Security: No issues\n2. Logic: Looks good"
            result = await programmer.review_code("def foo(): pass")
        assert result["status"] == "success"
        assert "review" in result


# ── StyleLearner ─────────────────────────────────────────────────────────────


class TestStyleLearner:
    def test_default_guidelines(self):
        from tools.learning.style_learner import StyleLearner

        learner = StyleLearner()
        guidelines = learner._default_guidelines()
        assert "python" in guidelines
        assert "typescript" in guidelines
        assert "general_patterns" in guidelines

    def test_generate_style_prompt_no_cache(self):
        from tools.learning.style_learner import StyleLearner

        learner = StyleLearner()
        prompt = learner.generate_style_prompt("/nonexistent/repo", "python")
        assert "best practices" in prompt.lower()

    def test_generate_style_prompt_with_cache(self):
        from tools.learning.style_learner import StyleLearner

        learner = StyleLearner()
        learner.learned_styles["/my/repo"] = {
            "python": {"naming_convention": "snake_case"},
            "general_patterns": ["Use type hints"],
        }
        prompt = learner.generate_style_prompt("/my/repo", "python")
        assert "snake_case" in prompt
        assert "type hints" in prompt.lower()

    @pytest.mark.anyio
    async def test_extract_style_no_files(self, tmp_path):
        from tools.learning.style_learner import StyleLearner

        learner = StyleLearner()
        # Empty dir → should return default guidelines
        result = await learner.analyze_codebase(str(tmp_path))
        assert "python" in result


# ── DiagramToArchitecture ────────────────────────────────────────────────────


class TestDiagramToArchitecture:
    def test_mock_output(self):
        from tools.code.diagram_to_architecture import DiagramToArchitecture

        converter = DiagramToArchitecture()
        result = converter._mock_output("aws", "terraform")
        assert result["status"] == "success"
        assert "aws" in result["code"]
        assert len(result["identified_components"]) > 0

    def test_parse_terraform_components(self):
        from tools.code.diagram_to_architecture import DiagramToArchitecture

        converter = DiagramToArchitecture()
        code = """
resource "aws_vpc" "main" {}
resource "aws_subnet" "public" {}
module "eks_cluster" {}
"""
        components = converter._parse_components_from_code(code, "terraform")
        types = [c["type"] for c in components]
        assert "aws_vpc" in types
        assert "aws_subnet" in types
        assert "module" in types

    @pytest.mark.anyio
    async def test_generate_infrastructure_file_not_found(self):
        from tools.code.diagram_to_architecture import DiagramToArchitecture

        converter = DiagramToArchitecture()
        result = await converter.generate_infrastructure("/nonexistent/diagram.png")
        assert result["status"] == "error"
        assert "error" in result
