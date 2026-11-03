from core.immune_system import ImmuneSystemScanner


def test_immune_system_passes_safe_code():
    scanner = ImmuneSystemScanner()
    code = """
class DataFormatter:
    async def execute(self, kwargs) -> dict:
        val = kwargs.get("val", 0)
        return {"result": val * 10}
"""
    res = scanner.scan_code(code)
    assert res["safe"] is True
    assert res["error"] is None


def test_immune_system_blocks_banned_imports():
    scanner = ImmuneSystemScanner()
    code = """
import os
class MaliciousSkill:
    async def execute(self, kwargs) -> dict:
        os.system("echo test")
        return {}
"""
    res = scanner.scan_code(code)
    assert res["safe"] is False
    assert "Banned root import" in res["error"]


def test_immune_system_blocks_eval_functions():
    scanner = ImmuneSystemScanner()
    code = """
class ExploitSkill:
    async def execute(self, kwargs) -> dict:
        eval("print('exploited')")
        return {}
"""
    res = scanner.scan_code(code)
    assert res["safe"] is False
    assert "banned security identifier" in res["error"]


def test_immune_system_blocks_dunder_reflection():
    scanner = ImmuneSystemScanner()
    code = """
class ExploitSkill:
    async def execute(self, kwargs) -> dict:
        instance = kwargs.get("obj")
        fn = getattr(instance, "__dict__")
        return {}
"""
    res = scanner.scan_code(code)
    assert res["safe"] is False
    assert "banned security identifier" in res["error"] or "reflection" in res["error"]
