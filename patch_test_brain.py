import types
import os

with open('backend/tests/core/test_brain.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix 1: async_route_and_generate
code = code.replace(
    '    router.async_route_and_generate = mock_async_route\n    res = router.route_and_generate("hello", "coding")\n    assert res["success"] is True\n    assert res["text"] == "local response"',
    '    with patch.object(router, "async_route_and_generate", mock_async_route):\n        res = router.route_and_generate("hello", "coding")\n        assert res["success"] is True\n        assert res["text"] == "local response"'
)

# Fix 2: cot_reasoner and route_and_generate
code = code.replace(
    '    router.cot_reasoner = MagicMock()\n    router.cot_reasoner.refine_loop.return_value = {',
    '    mock_cot = MagicMock()\n    mock_cot.refine_loop.return_value = {'
)
code = code.replace(
    '    router.cot_reasoner.verify.return_value = {"matches": True}',
    '    mock_cot.verify.return_value = {"matches": True}'
)
code = code.replace(
    '    router.route_and_generate = types.MethodType(fake_route, router)\n    result = router.route_and_generate_with_cot("1+1?", task_type="math")',
    '    with patch.object(router, "cot_reasoner", mock_cot), patch.object(router, "route_and_generate", types.MethodType(fake_route, router)):\n        result = router.route_and_generate_with_cot("1+1?", task_type="math")'
)
# Indent the assertions inside the context manager
code = code.replace(
    '        result = router.route_and_generate_with_cot("1+1?", task_type="math")\n\n    assert result["success"] is True\n    assert "reasoning" in result\n    assert result["reasoning"]["iterations"] == 1\n    assert result["reasoning"]["final_answer"] == "42"\n    assert "cot_verification" in result\n    assert result["text"] == "<answer>42</answer>"',
    '        result = router.route_and_generate_with_cot("1+1?", task_type="math")\n\n        assert result["success"] is True\n        assert "reasoning" in result\n        assert result["reasoning"]["iterations"] == 1\n        assert result["reasoning"]["final_answer"] == "42"\n        assert "cot_verification" in result\n        assert result["text"] == "<answer>42</answer>"'
)

# Fix 3: _local_rag
code = code.replace(
    '    router._local_rag = FakeRAG()\n    result = router.query_local_rag("python tutorial")\n\n    assert result["status"] == "ok"\n    assert len(result.get("matches", [])) == 2',
    '    with patch.object(router, "_local_rag", FakeRAG()):\n        result = router.query_local_rag("python tutorial")\n\n        assert result["status"] == "ok"\n        assert len(result.get("matches", [])) == 2'
)

# Fix 4: _stream_ollama
code = code.replace(
    '    router._stream_ollama = mock_stream\n\n    with patch.object(router, "_pick_provider", return_value=("ollama", "qwen")):\n        chunks = list(router.route_and_stream("test prompt", "general"))',
    '    with patch.object(router, "_stream_ollama", mock_stream), patch.object(router, "_pick_provider", return_value=("ollama", "qwen")):\n        chunks = list(router.route_and_stream("test prompt", "general"))'
)

with open('backend/tests/core/test_brain.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("File patched.")
