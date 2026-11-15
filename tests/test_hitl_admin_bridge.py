"""Unit tests for Gateway Frontend Compat HITL Approval & Notification Bridge."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gateway"))

import gateway.service.frontend_compat as fc
from gateway.service.frontend_compat import HitlRegisterPayload


class TestHitlAdminBridge(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        fc._pending_hitl.clear()
        fc._hitl_subscribers.clear()

    async def test_register_and_pending(self) -> None:
        payload = HitlRegisterPayload(
            id="pr-101",
            action_name="Auto-Merge PR #101 Review",
            command="gh pr merge 101 --auto --squash",
            module="ci/tiny_brain_guard",
            severity="high",
            context={"pr_number": 101, "run_id": 55555, "title": "feat: critical engine fix"},
        )
        reg_res = await fc.fe_hitl_register(payload)
        self.assertEqual(reg_res["status"], "ok")
        self.assertEqual(reg_res["record"]["id"], "pr-101")

        pending = await fc.fe_hitl_pending()
        self.assertIsInstance(pending, list)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], "pr-101")
        self.assertEqual(pending[0]["status"], "pending")

    async def test_approve_pr_actions(self) -> None:
        payload = HitlRegisterPayload(
            id="pr-102",
            action_name="Auto-Merge PR #102 Review",
            severity="high",
            context={"pr_number": 102, "run_id": 66666},
        )
        await fc.fe_hitl_register(payload)

        with patch.object(fc, "_gh") as mock_gh:
            # Mock pending deployments check & approval
            mock_gh.side_effect = [
                (200, [{"environment": {"id": 1234, "name": "production"}}]),  # GET pending_deployments
                (200, {"status": "approved"}),                                   # POST pending_deployments
                (200, {"state": "APPROVED"}),                                    # POST pulls/102/reviews
            ]
            res = await fc.fe_hitl_approve("pr-102")
            self.assertEqual(res["status"], "approved")
            self.assertEqual(mock_gh.call_count, 3)

        # After approval, pending list must no longer contain pr-102
        pending = await fc.fe_hitl_pending()
        self.assertEqual(len(pending), 0)

    async def test_reject_pr_actions(self) -> None:
        payload = HitlRegisterPayload(
            id="pr-103",
            action_name="Auto-Merge PR #103 Review",
            severity="high",
            context={"pr_number": 103, "run_id": 77777},
        )
        await fc.fe_hitl_register(payload)

        # Mock request with JSON body
        mock_req = MagicMock(spec=Request)
        mock_req.json = asyncio.iscoroutinefunction(lambda: None)
        async def fake_json():
            return {"reason": "Manual audit found security vulnerability"}
        mock_req.json = fake_json

        with patch.object(fc, "_gh") as mock_gh:
            mock_gh.side_effect = [
                (200, [{"environment": {"id": 1234}}]),  # GET pending_deployments
                (200, {"status": "rejected"}),            # POST pending_deployments
                (200, {"state": "CHANGES_REQUESTED"}),    # POST pulls/103/reviews
            ]
            res = await fc.fe_hitl_reject("pr-103", request=mock_req)
            self.assertEqual(res["status"], "rejected")
            self.assertIn("rejected", res["message"])

        pending = await fc.fe_hitl_pending()
        self.assertEqual(len(pending), 0)

    async def test_control_plane_hitl_and_resolve(self) -> None:
        payload = HitlRegisterPayload(
            id="pr-104",
            action_name="Auto-Merge PR #104",
            severity="medium",
            context={"pr_number": 104},
        )
        await fc.fe_hitl_register(payload)

        cp = await fc.cp_hitl()
        self.assertEqual(cp["status"], "ok")
        self.assertEqual(len(cp["tickets"]), 1)

        mock_req = MagicMock(spec=Request)
        async def fake_json():
            return {"decision": "approved"}
        mock_req.json = fake_json

        with patch.object(fc, "_gh", return_value=(200, {"ok": True})):
            resolve_res = await fc.cp_hitl_resolve("pr-104", request=mock_req)
            self.assertEqual(resolve_res["status"], "approved")

    async def test_sse_stream_broadcast(self) -> None:
        sse_resp = await fc.fe_stream_hitl()
        self.assertEqual(sse_resp.media_type, "text/event-stream")


if __name__ == "__main__":
    unittest.main()
