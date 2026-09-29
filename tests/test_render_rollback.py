# বাংলা মন্তব্য: Render Rollback Engine-এর hermetic পিন-টেস্ট (#2421 seq:3)।
# রোলব্যাক সিদ্ধান্ত লজিক (পূর্বসূরি live deploy শনাক্তকরণ, fail-closed চুক্তি)
# নেটওয়ার্ক ছাড়াই যাচাই — প্রকৃত Render API কল নেই।

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/deploy/render_rollback.py"


def _load():
    # বাংলা মন্তব্য: render_client import sys.path-ট্রিকের উপর দাঁড়িয়েছে —
    # টেস্টেও সেই পাথ দরকার; বাকি পক্ষে module import ব্যর্থ হবে।
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("render_rollback_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("render_rollback_under_test", mod)
    spec.loader.exec_module(mod)
    return mod


def _deploy(did: str, status: str, created: str, commit: str | None = None) -> dict:
    # বাংলা মন্তব্য: commit না দিলে id থেকে ডিরাইভ করা হয় (c<d> কনভেনশন)।
    return {
        "id": did,
        "status": {"value": status},
        "createdAt": created,
        "commit": {"id": commit if commit is not None else "c" + did, "message": f"msg {did}"},
    }


def test_picks_previous_live_excluding_newest() -> None:
    mod = _load()
    deploys = [
        _deploy("d3", "live", "2026-09-28T10:00:00Z"),
        _deploy("d2", "live", "2026-09-27T10:00:00Z"),
        _deploy("d1", "build_failed", "2026-09-26T10:00:00Z"),
    ]
    planner = mod.RollbackPlanner(deploys)
    bad = planner.pick_bad_deploy()
    target = planner.find_rollback_target(exclude_deploy_id=bad)
    assert bad == "d3"
    assert target["id"] == "d2"
    assert target["commit"]["id"] == "cd2"


def test_skips_failed_and_finds_older_live() -> None:
    # বাংলা মন্তব্য: মাঝখানে build_failed থাকলেও সর্বশেষ live পূর্বসূরিই টার্গেট।
    mod = _load()
    deploys = [
        _deploy("d4", "live", "2026-09-28T10:00:00Z"),
        _deploy("d3", "build_failed", "2026-09-28T09:00:00Z"),
        _deploy("d2", "live", "2026-09-27T10:00:00Z"),
    ]
    planner = mod.RollbackPlanner(deploys)
    target = planner.find_rollback_target(exclude_deploy_id="d4")
    assert target["id"] == "d2"


def test_fail_closed_when_no_stable_predecessor() -> None:
    # বাংলা মন্তব্য: স্থিতিশীল পূর্বসূরি নেই → অন্ধ revert নয়, স্পষ্ট ব্যর্থতা।
    mod = _load()
    deploys = [_deploy("d1", "build_failed", "2026-09-26T10:00:00Z")]
    planner = mod.RollbackPlanner(deploys)
    try:
        planner.find_rollback_target()
        raise AssertionError("fail-closed চুক্তি ভাঙা — ব্যর্থতা দরকার ছিল")
    except RuntimeError as err:
        assert "অন্ধ" in str(err) or "অ্যাডমিন" in str(err) or "টার্গেট" in str(err)


def test_fail_closed_when_commit_id_unknown() -> None:
    # বাংলা মন্তব্য: auto-deploy-এ commit অজানা হলে অন্ধ রোলব্যাক নিষিদ্ধ।
    mod = _load()
    deploys = [
        _deploy("d3", "live", "2026-09-28T10:00:00Z"),
        # বাংলা মন্তব্য: commit="" = Render auto-deploy যেখানে commitId অজানা।
        _deploy("d2", "live", "2026-09-27T10:00:00Z", commit=""),
    ]
    client = MagicMock()
    client.list_deploys.return_value = deploys
    client.default_service_id = "srv-x"
    try:
        mod.execute_rollback(client, service_id=None, dry_run=False, poll_timeout_sec=1)
        raise AssertionError("commitId-অজানা অবস্থায় রোলব্যাক হয়েছে — fail-closed ভাঙা")
    except RuntimeError as err:
        assert "commitId" in str(err)


def test_dry_run_writes_nothing() -> None:
    # বাংলা মন্তব্য: dry-run-এ কোনো POST যাবে না — শুধু পরিকল্পনা রিটার্ন।
    mod = _load()
    deploys = [
        _deploy("d3", "live", "2026-09-28T10:00:00Z"),
        _deploy("d2", "live", "2026-09-27T10:00:00Z"),
    ]
    client = MagicMock()
    client.list_deploys.return_value = deploys
    client.default_service_id = "srv-x"
    plan = mod.execute_rollback(client, service_id=None, dry_run=True, poll_timeout_sec=1)
    assert plan["result"].startswith("DRY-RUN")
    client.request.assert_not_called()  # কোনো write নেই
    assert json.dumps(plan, ensure_ascii=False)  # JSON-সিরিয়ালাইজেবল
