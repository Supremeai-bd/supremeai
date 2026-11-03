"""Governance tests for the RLHF pipeline (Constitution: Verification Before Trust).

বাংলা: যাচাই করে — ভুয়া preference record আর ভুয়া "simulation success" আর
কখনো ফেরত আসবে না। এটা HUMAN_BEHAVIOR_ALIGNMENT doc-এর Phase 3 গেটের ভিত্তি।
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from unittest.mock import patch


def _make_pipeline(tmpdir: str):
    from tools.learning.rlhf_pipeline import RLHFPipeline

    return RLHFPipeline(storage_dir=tmpdir)


class TestRLHFGovernance(unittest.IsolatedAsyncioTestCase):
    def test_no_mock_record_injected_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = _make_pipeline(tmp)
            # বাংলা: প্রথমেই কোনো ভুয়া "Hello" record ঢোকানো হয় না
            self.assertEqual(len(pipeline.preference_logs), 0)

    async def test_training_refuses_without_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = _make_pipeline(tmp)
            result = await pipeline.trigger_dpo_training()
            self.assertEqual(result["status"], "error")
            self.assertIn("No preference data", result["error"])

    async def test_no_simulated_success_when_trl_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = _make_pipeline(tmp)
            # বাংলা: বাস্তব রেকর্ড রেখে TRL-উপস্থিতি simulate করা হয়
            pipeline.record_preference("real prompt", "good answer", "bad answer")
            fake_spec = importlib.util.spec_from_loader("trl", loader=None)
            real_find_spec = importlib.util.find_spec

            def _pick(name, *args, **kwargs):
                if name in {"trl", "torch", "transformers"}:
                    return fake_spec
                return real_find_spec(name, *args, **kwargs)

            with patch.object(importlib.util, "find_spec", side_effect=_pick):
                result = await pipeline.trigger_dpo_training()
            # আগে এখানে ভুয়া "simulation success" আসত — এখন সৎ উত্তর
            self.assertNotEqual(
                result.get("message", ""),
                "Local DPO training simulation success using TRL library.",
            )
            self.assertIn(result["status"], {"not_implemented", "error"})


if __name__ == "__main__":
    unittest.main()
