from unittest.mock import AsyncMock, patch

import pytest

from engine.tree_of_thought import ThoughtNode, TreeOfThoughtReasoner


@pytest.mark.asyncio
async def test_tree_of_thought_reasoning():
    """Verify ToT engine evaluates branches and selects best thought."""
    reasoner = TreeOfThoughtReasoner(max_depth=3, num_branches=3)

    # We mock the internal _generate and _score methods since we don't want to hit real LLMs in unit tests yet
    with patch.object(
        reasoner, "_generate_initial_thoughts", new_callable=AsyncMock
    ) as mock_generate:
        with patch.object(reasoner, "_score_thoughts", new_callable=AsyncMock) as mock_score:
            mock_generate.return_value = [
                ThoughtNode(thought_id="1", content="Strategy A", score=0.0, depth=1),
                ThoughtNode(thought_id="2", content="Strategy B", score=0.0, depth=1),
            ]

            mock_score.return_value = [
                ThoughtNode(thought_id="1", content="Strategy A", score=0.6, depth=1),
                ThoughtNode(thought_id="2", content="Strategy B", score=0.9, depth=1),
            ]

            result = await reasoner.reason("How to optimize this database?")

            assert result["problem"] == "How to optimize this database?"
            assert result["best_thought"] == "Strategy B"
            assert result["confidence_score"] == 0.9
            assert result["total_branches_explored"] == 2
