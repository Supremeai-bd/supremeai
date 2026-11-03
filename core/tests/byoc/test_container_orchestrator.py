import pytest

from byoc.container_orchestrator import ContainerOrchestrator


class TestContainerOrchestrator:
    @pytest.mark.asyncio
    async def test_deploy_without_terraform_fails_honestly(self):
        # বাংলা মন্তব্য: terraform না থাকলে আর ভুয়া URL সহ "deployed" আসবে না —
        # সৎ failed (audit B-04 fix)।
        from unittest.mock import patch

        orchestrator = ContainerOrchestrator()
        with patch("shutil.which", return_value=None):
            result = await orchestrator.deploy("user1", "skill_v1")
            assert result["status"] == "failed"
            assert "Terraform is not installed" in result["error"]
            assert result["user_id"] == "user1"
            assert result["skill"] == "skill_v1"
            assert result["mode"] == "unavailable"

    @pytest.mark.asyncio
    async def test_deploy_live_success_returns_real_url(self):
        # বাংলা মন্তব্য: terraform থাকলে আসল output URL পার্স করে দেয় (blocking
        # subprocess এখন asyncio.to_thread-এ)।
        from unittest.mock import patch

        orchestrator = ContainerOrchestrator()
        fake_outputs = [
            type("R", (), {"stdout": "init ok", "stderr": ""})(),
            type("R", (), {"stdout": "apply ok", "stderr": ""})(),
            type(
                "R",
                (),
                {
                    "stdout": '{"service_url": {"value": "https://real-url.a.run.app"}}',
                    "stderr": "",
                },
            )(),
        ]

        def _fake_run(*args, **kwargs):
            return fake_outputs.pop(0)

        with (
            patch("shutil.which", return_value="/usr/bin/terraform"),
            patch("subprocess.run", side_effect=_fake_run),
        ):
            result = await orchestrator.deploy("user1", "skill_v1")
            assert result["status"] == "deployed"
            assert result["service_url"] == "https://real-url.a.run.app"
            assert result["mode"] == "live"

    @pytest.mark.asyncio
    async def test_deploy_live_missing_service_url_refuses_to_fabricate(self):
        from unittest.mock import patch

        orchestrator = ContainerOrchestrator()
        fake_outputs = [
            type("R", (), {"stdout": "init ok", "stderr": ""})(),
            type("R", (), {"stdout": "apply ok", "stderr": ""})(),
            type("R", (), {"stdout": "{}", "stderr": ""})(),  # no service_url
        ]

        def _fake_run(*args, **kwargs):
            return fake_outputs.pop(0)

        with (
            patch("shutil.which", return_value="/usr/bin/terraform"),
            patch("subprocess.run", side_effect=_fake_run),
        ):
            result = await orchestrator.deploy("user1", "skill_v1")
            assert result["status"] == "failed"
            assert "service_url" in result["error"]

    @pytest.mark.asyncio
    async def test_rollback_without_terraform_fails_honestly(self):
        # বাংলা মন্তব্য: terraform না থাকলে আর "rolled_back" (simulated) বলা হবে না।
        from unittest.mock import patch

        orchestrator = ContainerOrchestrator()
        with patch("shutil.which", return_value=None):
            result = await orchestrator.rollback("deploy_abc")
            assert result["status"] == "failed"
            assert "Terraform is not installed" in result["error"]
            assert result["deployment_id"] == "deploy_abc"

    @pytest.mark.asyncio
    async def test_rollback_destroy_failure_is_honest(self):
        # বাংলা মন্তব্য: terraform destroy ব্যর্থ হলেও আগে "rolled_back" বলত — এখন failed।
        from unittest.mock import patch

        orchestrator = ContainerOrchestrator()

        def _boom(*args, **kwargs):
            raise RuntimeError("destroy exploded")

        with (
            patch("shutil.which", return_value="/usr/bin/terraform"),
            patch("subprocess.run", side_effect=_boom),
        ):
            result = await orchestrator.rollback("deploy_abc")
            assert result["status"] == "failed"
            assert "destroy exploded" in result["error"]

    @pytest.mark.asyncio
    async def test_rollback_live_success(self):
        from unittest.mock import patch

        orchestrator = ContainerOrchestrator()
        with (
            patch("shutil.which", return_value="/usr/bin/terraform"),
            patch("subprocess.run", return_value=type("R", (), {"stdout": "", "stderr": ""})()),
        ):
            result = await orchestrator.rollback("deploy_abc")
            assert result["status"] == "rolled_back"
            assert result["mode"] == "live"
