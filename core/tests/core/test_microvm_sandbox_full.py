"""Full-coverage tests for core/microvm_sandbox.py (Task 7 wave-2).

All subprocess/docker/firecracker interaction is mocked; the sandbox root is a
tmp_path validated via the module's own whitelist helper (patched whitelist).
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.microvm_sandbox as mv
from core.microvm_sandbox import (
    MicroVMSandbox,
    _ast_validate_code,
    _safe_vm_path,
    _validate_sandbox_root,
    _validate_vm_id,
    execute_code_securely,
    get_sandbox,
)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """MicroVMSandbox rooted at a whitelisted tmp dir; no VM runtimes on PATH.

    settings is replaced wholesale with a SimpleNamespace (pydantic Settings
    teardown crashes when monkeypatching attributes that never existed), and
    ResourceGuard path checks are relaxed for pytest tmp dirs.
    """
    from types import SimpleNamespace

    root = tmp_path / "sandboxes"
    monkeypatch.setattr(mv, "_SANDBOX_ROOT_WHITELIST", frozenset({str(root)}))
    ns = SimpleNamespace(
        firecracker_path="/usr/bin/firecracker",
        gvisor_path="/usr/bin/runsc",
        sandbox_root=str(root),
        allow_sandbox_fallback=True,
        firecracker_rootfs_template=None,
    )
    monkeypatch.setattr(mv, "settings", ns)
    import core.security.resource_guard as rg

    monkeypatch.setattr(rg.ResourceGuard, "verify_path", staticmethod(lambda p: p), raising=False)
    import shutil as _shutil

    monkeypatch.setattr(_shutil, "which", lambda name: None)
    s = MicroVMSandbox()
    return s


class TestValidators:
    def test_validate_sandbox_root_ok(self, tmp_path, monkeypatch):
        root = tmp_path / "sandboxes"
        monkeypatch.setattr(mv, "_SANDBOX_ROOT_WHITELIST", frozenset({str(root)}))
        assert _validate_sandbox_root(str(root)) == root.resolve()

    def test_validate_sandbox_root_rejects(self, tmp_path):
        with pytest.raises(ValueError, match="whitelist"):
            _validate_sandbox_root(str(tmp_path / "evil"))

    @pytest.mark.parametrize("vm_id", ["abc-123_X", "a", "supremeai-vm-0123456789abcdef0123"])
    def test_validate_vm_id_ok(self, vm_id):
        assert _validate_vm_id(vm_id) == vm_id

    @pytest.mark.parametrize("vm_id", ["", "../evil", "has space", "dot.dot", "x" * 65, "slash/"])
    def test_validate_vm_id_rejects(self, vm_id):
        with pytest.raises(ValueError, match="Invalid vm_id"):
            _validate_vm_id(vm_id)

    def test_generate_vm_id_valid(self):
        vm_id = MicroVMSandbox._generate_vm_id()
        assert vm_id.startswith("supremeai-vm-")
        assert _validate_vm_id(vm_id) == vm_id

    def test_safe_vm_path(self, tmp_path, monkeypatch):
        import core.security.resource_guard as rg

        monkeypatch.setattr(
            rg.ResourceGuard, "verify_path", staticmethod(lambda p: p), raising=False
        )
        root = tmp_path / "sb"
        root.mkdir()
        p = _safe_vm_path(root, "vm1")
        assert p == (root / "vm1").resolve()

    def test_ast_validate_code_safe_and_unsafe(self):
        ok, reason = _ast_validate_code("print('hi')")
        assert ok is True
        bad, reason2 = _ast_validate_code("eval('2+2')")
        assert bad is False
        assert reason2


class TestMicroVMSandboxBasics:
    def test_init_creates_root_and_flags(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        root = tmp_path / "sandboxes"
        monkeypatch.setattr(mv, "_SANDBOX_ROOT_WHITELIST", frozenset({str(root)}))
        monkeypatch.setattr(
            mv,
            "settings",
            SimpleNamespace(
                firecracker_path="fc",
                gvisor_path="runsc",
                sandbox_root=str(root),
                allow_sandbox_fallback=True,
            ),
        )
        s = MicroVMSandbox()
        assert s.network_disabled is True
        assert s.auto_destroy is True
        assert s.allow_fallback is True
        assert root.exists()

    def test_check_microvm_available_priority(self, sandbox, monkeypatch):
        assert sandbox._check_microvm_available() is None
        monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/x" if n == "runsc" else None)
        assert sandbox._check_microvm_available() == "gvisor"
        monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/fc")
        assert sandbox._check_microvm_available() == "firecracker"

    def test_health_check(self, sandbox):
        h = asyncio.run(sandbox.health_check())
        assert h["status"] == "unavailable"
        assert h["provider"] == "none"
        assert h["network_disabled"] is True

    def test_destroy_vm_dir_missing_ok(self, sandbox, tmp_path):
        sandbox._destroy_vm_dir(tmp_path / "ghost")  # no raise

    def test_destroy_vm_dir_error_suppressed(self, sandbox, tmp_path, monkeypatch):
        d = tmp_path / "vm"
        d.mkdir()
        monkeypatch.setattr("shutil.rmtree", MagicMock(side_effect=RuntimeError("x")))
        sandbox._destroy_vm_dir(d)  # logged, not raised


class TestExecuteAsync:
    async def test_unsafe_code_blocked_by_ast(self, sandbox):
        res = await sandbox.execute_async("eval('x')")
        assert res["success"] is False
        assert res["provider"] == "sandbox_scanner"
        assert "AST" in res["error"]

    async def test_no_runtime_no_fallback(self, sandbox, monkeypatch):
        sandbox.allow_fallback = False
        emitted = []
        monkeypatch.setattr(
            "core.microvm_sandbox.error_event_bus",
            MagicMock(emit=lambda ev: emitted.append(ev)),
        )
        res = await sandbox.execute_async("print(1)")
        assert res["success"] is False
        assert res["provider"] == "none"
        assert "security enforcement" in res["error"]
        assert len(emitted) == 1

    async def test_path_validation_failure(self, sandbox, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda n: None)
        monkeypatch.setattr(mv, "_safe_vm_path", MagicMock(side_effect=ValueError("bad path")))
        res = await sandbox.execute_async("print(1)")
        assert res["success"] is False
        assert "bad path" in res["error"]

    async def test_unexpected_error_reported(self, sandbox, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda n: None)
        monkeypatch.setattr(
            sandbox, "_run_docker_fallback", AsyncMock(side_effect=RuntimeError("boom"))
        )
        emitted = []
        monkeypatch.setattr(
            "core.microvm_sandbox.error_event_bus",
            MagicMock(emit=lambda ev: emitted.append(ev)),
        )
        res = await sandbox.execute_async("print(1)")
        assert res["success"] is False
        assert res["provider"] == "docker"
        assert len(emitted) == 1

    async def test_cancelled_error_reraised(self, sandbox, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda n: None)
        monkeypatch.setattr(
            sandbox, "_run_docker_fallback", AsyncMock(side_effect=asyncio.CancelledError())
        )
        with pytest.raises(asyncio.CancelledError):
            await sandbox.execute_async("print(1)")

    async def test_docker_success_and_cleanup(self, sandbox, monkeypatch, tmp_path):
        sandbox.allow_fallback = True
        monkeypatch.setattr("shutil.which", lambda n: None)
        created = {}

        def fake_run(*a, **kw):
            # capture the temp file the sandbox wrote
            vol = [x for x in a[0] if isinstance(x, str) and ":/sandbox/code.py" in x]
            created["host"] = vol[0].split(":/sandbox")[0]
            r = MagicMock()
            r.returncode = 0
            r.stdout = "out"
            r.stderr = ""
            return r

        monkeypatch.setattr("subprocess.run", fake_run)
        res = await sandbox.execute_async("print('hi')")
        assert res["success"] is True
        assert res["provider"] == "docker-fallback"
        assert res["stdout"] == "out"
        assert not Path(created["host"]).exists()  # temp cleaned up

    async def test_docker_timeout(self, sandbox, monkeypatch):
        sandbox.allow_fallback = True
        monkeypatch.setattr("shutil.which", lambda n: None)
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=1)),
        )
        res = await sandbox.execute_async("print('hi')")
        assert res["success"] is False
        assert res["error"] == "Execution timeout"

    async def test_docker_generic_error(self, sandbox, monkeypatch):
        sandbox.allow_fallback = True
        monkeypatch.setattr("shutil.which", lambda n: None)
        monkeypatch.setattr("subprocess.run", MagicMock(side_effect=OSError("no docker")))
        res = await sandbox.execute_async("print('hi')")
        assert res["success"] is False
        assert res["provider"] == "docker-fallback"

    async def test_gvisor_success(self, sandbox, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda n: "/bin/runsc" if n == "runsc" else None)
        r = MagicMock()
        r.returncode = 0
        r.stdout = "g_out"
        r.stderr = "g_err"
        monkeypatch.setattr("subprocess.run", MagicMock(return_value=r))
        res = await sandbox.execute_async("print('g')")
        assert res["success"] is True
        assert res["provider"] == "gvisor"
        assert res["stdout"] == "g_out"

    async def test_gvisor_timeout_and_error(self, sandbox, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda n: "/bin/runsc" if n == "runsc" else None)
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(side_effect=subprocess.TimeoutExpired(cmd="runsc", timeout=1)),
        )
        res = await sandbox.execute_async("print('g')")
        assert res["error"] == "Execution timeout"

        monkeypatch.setattr("subprocess.run", MagicMock(side_effect=OSError("no gvisor")))
        res2 = await sandbox.execute_async("print('g')")
        assert res2["provider"] == "gvisor"
        assert res2["success"] is False

    async def test_firecracker_no_rootfs(self, sandbox, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda n: "/bin/fc" if n == "firecracker" else None)
        sandbox_root_ns = SimpleNamespace(
            **{**vars(mv.settings), "firecracker_rootfs_template": None}
        )
        monkeypatch.setattr(mv, "settings", sandbox_root_ns)
        res = await sandbox.execute_async("print('f')")
        assert res["success"] is False
        assert "rootfs template unavailable" in res["error"]
        assert res["provider"] == "firecracker"

    async def test_firecracker_full_run(self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setattr("shutil.which", lambda n: "/bin/fc" if n == "firecracker" else None)
        rootfs = tmp_path / "rootfs.ext4"
        monkeypatch.setattr(
            mv,
            "settings",
            SimpleNamespace(**{**vars(mv.settings), "firecracker_rootfs_template": str(rootfs)}),
        )
        r = MagicMock()
        r.returncode = 0
        r.stdout = "f_out"
        r.stderr = ""
        monkeypatch.setattr("subprocess.run", MagicMock(return_value=r))
        res = await sandbox.execute_async("print('f')")
        assert res["success"] is True
        assert res["provider"] == "firecracker"
        assert res["stdout"] == "f_out"

    async def test_firecracker_timeout_and_error(self, sandbox, monkeypatch, tmp_path):
        monkeypatch.setattr("shutil.which", lambda n: "/bin/fc" if n == "firecracker" else None)
        rootfs = tmp_path / "rootfs.ext4"
        monkeypatch.setattr(
            mv,
            "settings",
            SimpleNamespace(**{**vars(mv.settings), "firecracker_rootfs_template": str(rootfs)}),
        )
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(side_effect=subprocess.TimeoutExpired(cmd="firecracker", timeout=1)),
        )
        res = await sandbox.execute_async("print('f')")
        assert res["error"] == "Execution timeout"
        monkeypatch.setattr("subprocess.run", MagicMock(side_effect=OSError("fc broken")))
        res2 = await sandbox.execute_async("print('f')")
        assert res2["provider"] == "firecracker"

    async def test_firecracker_inner_ast_block(self, sandbox, monkeypatch, tmp_path):
        # code that passes outer check is re-checked inside _run_firecracker
        monkeypatch.setattr("shutil.which", lambda n: "/bin/fc" if n == "firecracker" else None)
        rootfs = tmp_path / "rootfs.ext4"
        monkeypatch.setattr(
            mv,
            "settings",
            SimpleNamespace(**{**vars(mv.settings), "firecracker_rootfs_template": str(rootfs)}),
        )
        with patch.object(
            mv, "_ast_validate_code", side_effect=[(True, ""), (False, "bad pattern")]
        ):
            res = await sandbox.execute_async("print('f')")
        assert res["success"] is False
        assert "AST validation failed" in res["error"]

    def test_create_microvm_config(self, sandbox, tmp_path):
        vm_dir = tmp_path / "vmdir"
        vm_dir.mkdir()
        cfg_path = sandbox._create_microvm_config(vm_dir, "vm-1", rootfs_template=None)
        assert cfg_path.exists()
        import json

        cfg = json.loads(cfg_path.read_text())
        assert cfg["network-interfaces"] == []
        assert cfg["machine-config"] == {"vcpu_count": 1, "mem_size_mib": 128}

    def test_auto_destroy_disabled_keeps_dir(self, sandbox, monkeypatch, tmp_path):
        sandbox.allow_fallback = True
        sandbox.auto_destroy = False
        monkeypatch.setattr("shutil.which", lambda n: None)
        r = MagicMock()
        r.returncode = 0
        monkeypatch.setattr("subprocess.run", MagicMock(return_value=r))
        asyncio.run(sandbox.execute_async("print(1)"))
        # vm dir under sandbox root survives
        assert any(sandbox.sandbox_root.iterdir())


class TestSingletonAndPublicAPI:
    def test_get_sandbox_lazy_singleton(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        root = tmp_path / "sandboxes"
        monkeypatch.setattr(mv, "_SANDBOX_ROOT_WHITELIST", frozenset({str(root)}))
        monkeypatch.setattr(
            mv,
            "settings",
            SimpleNamespace(
                firecracker_path="fc",
                gvisor_path="runsc",
                sandbox_root=str(root),
                allow_sandbox_fallback=True,
            ),
        )
        mv._sandbox_instance = None
        s1 = get_sandbox()
        s2 = get_sandbox()
        assert s1 is s2
        mv._sandbox_instance = None  # don't leak into other tests

    async def test_execute_code_securely_blocks_unsafe(self, monkeypatch):
        res = await execute_code_securely("__import__('os').system('ls')")
        assert res["success"] is False
        assert res["provider"] == "sandbox_scanner"

    async def test_execute_code_securely_delegates(self, monkeypatch):
        fake = MagicMock()
        fake.execute_async = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(mv, "get_sandbox", lambda: fake)
        res = await execute_code_securely("print(2)")
        assert res["success"] is True
        fake.execute_async.assert_awaited_once_with("print(2)", 30, "python")
