# tests/test_ephemeral_lifecycle.py
import pytest
from pathlib import Path
from backend.agents.ephemeral_executor import EphemeralExecutor


def test_ephemeral_executor_purges_files_strictly_on_finally():
    executor = EphemeralExecutor()
    skill_id = "test_transient_tool"

    dummy_code = """
def execute_tool(payload):
    return {"result": "Calculated transient data for " + payload}
    """

    # স্যান্ডবক্স মক বা রান লুপ এক্সিকিউশন
    # (যদি লোকাল ডকার রানিং না থাকে, সরাসরি সাবপ্রসেস এক্সেপশন ট্র্যাপ হবে, কিন্তু ফাইল মুছবেই)
    res = executor.execute_use_and_throw(skill_id, dummy_code, '"2040-eclipse"')

    # ভেরিফিকেশন: এক্সিকিউশন শেষে ডিরেক্টরিটি ফাইল সিস্টেম থেকে চিরতরে হাওয়া হয়েছে কিনা
    target_dir = Path(executor.ephemeral_dir) / skill_id
    assert target_dir.exists() is False
