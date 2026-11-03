from brain.autonomous_agent import AutonomousAgent


def test_plan_debug_keywords():
    agent = AutonomousAgent()
    plan = agent.plan("fix database connection error")
    assert plan["summary"] == "Investigate issue, propose fix, apply fix, verify."
    assert plan["steps"] == ["investigate", "propose_fix", "apply_fix", "verify"]


def test_plan_build_keywords():
    agent = AutonomousAgent()
    plan = agent.plan("create new API endpoint")
    assert plan["summary"] == "Scaffold implementation, implement core, add basic tests."
    assert plan["steps"] == ["scaffold", "implement", "basic_tests"]


def test_plan_analyze_keywords():
    agent = AutonomousAgent()
    plan = agent.plan("review code quality")
    assert plan["summary"] == "Read inputs, analyze structure, summarize findings."
    assert plan["steps"] == ["read_inputs", "analyze", "summarize"]


def test_plan_default():
    agent = AutonomousAgent()
    plan = agent.plan("do something random")
    assert plan["summary"] == "Default quick execution."
    assert plan["steps"] == ["execute", "summarize"]


def test_execute_simple():
    agent = AutonomousAgent()
    result = agent.execute("fix bug")
    assert "success" in result
    assert "steps" in result
    assert isinstance(result["steps"], list)


def test_execute_adds_to_history():
    agent = AutonomousAgent()
    agent.execute("test task")
    assert len(agent.history) == 1
    assert agent.history[0]["task"] == "test task"


def test_reflect_success():
    agent = AutonomousAgent()
    run = {"success": True, "steps": ["a", "b"], "errors": []}
    reflection = agent.reflect(run)
    assert reflection["success"] is True
    assert reflection["improvements"] == []


def test_reflect_failure():
    agent = AutonomousAgent()
    run = {"success": False, "steps": ["a"], "errors": ["some error"]}
    reflection = agent.reflect(run)
    assert len(reflection["failures"]) == 1
    assert len(reflection["improvements"]) == 1


def test_run_returns_combined():
    agent = AutonomousAgent()
    output = agent.run("build feature")
    assert "run" in output
    assert "reflection" in output
    assert output["run"]["success"] is True
