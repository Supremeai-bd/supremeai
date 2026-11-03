# বাংলা মন্তব্য: Style Learner-এর tree-sitter AST analysis ফাংশনালিটি টেস্ট।

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.learning.style_learner import StyleLearner


@pytest.mark.anyio
async def test_analyze_codebase_ast():
    # বাংলা মন্তব্য: Codebase-এর AST-level pattern বিশ্লেষণ টেস্ট
    learner = StyleLearner()

    with patch(
        "brain.model_router.ModelRouter.async_route_and_generate",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = {
            "text": '{"naming_convention": "snake_case", "function_length": 20, "import_style": "isort"}'
        }

        # Create a mock directory structure
        with patch("tools.style_learner.os.walk") as mock_walk:
            mock_walk.return_value = [("backend/tools", [], ["test.py"])]

            with patch("builtins.open", new_callable=MagicMock) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "def my_function():\n    pass"
                )

                result = await learner.analyze_codebase("backend/tools")

    assert result is not None
    assert "python" in result or "naming_convention" in result or "ast_patterns" in result


@pytest.mark.anyio
async def test_generate_with_style():
    # বাংলা মন্তব্য: ব্যবহারকারীর স্টাইল অনুযায়ী কোড জেনারেট করা হচ্ছে
    learner = StyleLearner()

    with patch(
        "brain.model_router.ModelRouter.async_route_and_generate",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = {
            "text": "def my_snake_case_function():\n    # Generated with user style\n    pass"
        }

        result = await learner.generate_with_style("Create a function", "user_123")

    assert result is not None
    assert result.get("status") == "success"
    assert "def" in result.get("code", "")


@pytest.mark.anyio
async def test_sync_team_style():
    # বাংলা মন্তব্য: টিম স্টাইল সিঙ্ক টেস্ট
    learner = StyleLearner()

    with patch(
        "brain.model_router.ModelRouter.async_route_and_generate",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = {"text": '{"python": {"naming_convention": "snake_case"}}'}

        with patch("tools.style_learner.os.walk") as mock_walk:
            mock_walk.return_value = [("backend/tools", [], ["test.py"])]
            with patch("builtins.open", new_callable=MagicMock) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "def my_function():\n    pass"
                )

                result = await learner.sync_team_style("backend/tools", "team_1")

    assert result is not None
    assert result.get("team_id") == "team_1"
