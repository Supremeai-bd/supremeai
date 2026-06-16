import os
import sys
import tempfile
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.docker_sandbox import DockerSandbox
from tools.cost_auditor import CostAuditor
from tools.plan_sorter import PlanSorter
from tools.health_checker import HealthChecker
from core.audit_logger import AuditLogger

def test_docker_sandbox_security():
    sandbox = DockerSandbox()
    # Test harmful command block
    res = sandbox.execute_command("rm -rf /")
    assert res["success"] is False
    assert "Security block" in res["error"]

def test_docker_sandbox_simulated_run():
    sandbox = DockerSandbox()
    sandbox.docker_available = False
    res = sandbox.execute_command("echo hello")
    assert res["success"] is True
    assert "hello" in res.get("stdout", "").strip()

def test_cost_auditor_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_mem.db")
        auditor = CostAuditor(db_path)
        report = auditor.generate_report()
        
        assert os.path.exists(report["text_report"])
        assert os.path.exists(report["image_report"])

def test_plan_sorter():
    with tempfile.TemporaryDirectory() as tmpdir:
        inbox = os.path.join(tmpdir, "inbox")
        outdir = os.path.join(tmpdir, "output")
        os.makedirs(inbox, exist_ok=True)
        
        # Create a mock urgent plan
        with open(os.path.join(inbox, "urgent_plan.md"), "w", encoding="utf-8") as f:
            f.write("URGENT: Deploy backup server ASAP.")
            
        # Create a mock bug plan
        with open(os.path.join(inbox, "bug_plan.md"), "w", encoding="utf-8") as f:
            f.write("Fix authentication bug.")
            
        sorter = PlanSorter(inbox, outdir)
        categorized = sorter.sort_and_organize_plans()
        
        assert "urgent_plan.md" in categorized["Urgent"]
        assert "bug_plan.md" in categorized["Bug"]

def test_health_checker():
    checker = HealthChecker()
    report = checker.run_health_check()
    assert "overall_status" in report
    assert "dependencies" in report

def test_audit_logger():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        logger = AuditLogger(db_path)
        logger.log_decision(
            action_type="test_action",
            decision_details="details_here",
            reasoning="reasoning_here"
        )
        trail = logger.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["action_type"] == "test_action"
        assert trail[0]["decision_details"] == "details_here"
        assert trail[0]["reasoning"] == "reasoning_here"

