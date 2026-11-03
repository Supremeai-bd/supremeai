"""Unit tests for MultiPlatformOrchestrator path containment and shell injection security safeguards.

# বাংলা: MultiPlatformOrchestrator-এর পাথ ট্রাভার্সাল ডিফেন্স ও শেল ইনজেকশন প্রোটেকশন টেস্ট।
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from core.multi_platform_orchestrator import MultiPlatformOrchestrator


def test_prefix_collision_path_traversal_is_blocked():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    সুনির্দিষ্ট ভাইবোন ডিরেক্টরি (যেমন workspace_secret) ব্যবহার করে স্ট্রিং প্রিফিক্স ট্র্যাপ
    বাইপাস করার চেষ্টা কড়াভাবে ব্লক হওয়া নিশ্চিতকরণ।
    """
    orchestrator = MultiPlatformOrchestrator()

    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        workspace = base_path / "workspace"
        workspace.mkdir()

        # Target resolves to tmp_dir/workspace_secret/leak.txt
        # Old startswith(str(root)) check would allow this because "/tmp/.../workspace_secret"
        # starts with "/tmp/.../workspace".
        raw_output = """
### ../workspace_secret/leak.txt
```python
stolen_data = True
```
"""
        parsed_plan = orchestrator.parse_ai_output(raw_output)
        res = orchestrator.apply_plan_locally(parsed_plan, workspace_root=workspace)

        assert not (base_path / "workspace_secret" / "leak.txt").exists()
        assert any(
            "Security: Path traversal attempt blocked" in err for err in res.errors
        )


def test_safe_local_plan_execution_and_shlex_verification():
    """
    বাংলা সারসংক্ষেপ:
    ------------------
    বৈধ ইন-ট্রি ফাইল সঠিক স্থানে তৈরি হওয়া এবং ভেরিফিকেশন কমান্ড নিরাপদে চলা যাচাই।
    """
    orchestrator = MultiPlatformOrchestrator()

    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir) / "app"
        workspace.mkdir()

        raw_output = """
### src/main.py
```python
print("hello supremeai")
```

Verify test:
```bash
python -c "print('test_passed')"
```
"""
        plan = orchestrator.parse_ai_output(raw_output)
        res = orchestrator.apply_plan_locally(plan, workspace_root=workspace)

        assert "src/main.py" in res.applied_files
        assert (workspace / "src" / "main.py").read_text() == 'print("hello supremeai")'
        assert res.verification_passed is True
        assert "test_passed" in res.verification_output
