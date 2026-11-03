import json
from unittest.mock import patch

import pytest

try:
    from skill_loader import SkillLoader
    from skills.registry import SkillRegistry

    from core.self_evolution.auto_skill_creator import AutoSkillCreator
    from skills.installer import SkillInstaller

    HAS_SKILLS_INSTALLER = True
except (ImportError, ModuleNotFoundError):
    HAS_SKILLS_INSTALLER = False

pytestmark = pytest.mark.skipif(
    not HAS_SKILLS_INSTALLER, reason="skills.installer module not available in environment"
)


@pytest.fixture
def clean_dynamic_skills(tmp_path):
    # Set up temp dir for registry, dynamic and quarantine folders
    registry = SkillRegistry()

    # Configure custom installer with temp skills_dir
    installer = SkillInstaller(registry=registry, skills_dir=str(tmp_path / "dynamic"))

    loader = SkillLoader(registry=registry, installer=installer)
    loader.skills_dir = tmp_path / "dynamic"
    loader.skills_dir.mkdir(parents=True, exist_ok=True)

    # Mock SkillInstaller constructor to return our temp configured installer
    with patch("core.self_evolution.auto_skill_creator.SkillInstaller", return_value=installer):
        yield loader, registry, installer


MOCK_AI_RESPONSE_JSON = {
    "code": "class SentimentAnalyzer:\n    async def execute(self, kwargs):\n        return {'sentiment': 'positive'}\n",
    "schema": {
        "metadata": {
            "name": "SentimentAnalyzer",
            "version": "1.0.0",
            "description": "Mocked sentiment analyzer.",
            "author": "supremeai_agent_id",
            "tags": [],
        },
        "interface": {
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
        },
        "execution": {
            "runtime": "python3.11",
            "entry_point": "main.execute",
            "dependencies": [],
            "timeout_seconds": 30,
        },
        "validation": {
            "tests": [
                {
                    "input": {"text": "I love this!"},
                    "expected_output": {"sentiment": "positive"},
                }
            ],
            "security_level": "sandboxed",
        },
    },
}


@pytest.mark.anyio
async def test_pipeline_success(clean_dynamic_skills, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_SANDBOX_FALLBACK", "true")
    loader, _registry, _installer = clean_dynamic_skills

    async def mock_acompletion(*args, **kwargs):
        return {"success": True, "text": json.dumps(MOCK_AI_RESPONSE_JSON)}

    with patch("core.llm.llm_gateway.llm_gateway.acompletion", new=mock_acompletion):
        creator = AutoSkillCreator()
        result = await creator.generate_and_deploy_skill(
            user_demand="Analyze reviews sentiment", skill_name="SentimentAnalyzer"
        )
        assert result["success"] is True, result.get("error", "No error info provided")
        assert result["skill_name"] == "SentimentAnalyzer"

        # Verify dynamic loading and execution works after installation
        mod = loader.load("SentimentAnalyzer")
        instance = mod.SentimentAnalyzer()
        exec_result = await instance.execute({"text": "I love this!"})
        assert exec_result == {"sentiment": "positive"}


@pytest.mark.anyio
async def test_pipeline_validation_mismatch(clean_dynamic_skills, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_SANDBOX_FALLBACK", "true")
    loader, _registry, _installer = clean_dynamic_skills

    # Modify mock JSON so that execute return value mismatch validation expected output
    mismatch_json = MOCK_AI_RESPONSE_JSON.copy()
    mismatch_json["code"] = (
        "class SentimentAnalyzer:\n    async def execute(self, kwargs):\n        return {'sentiment': 'negative'}\n"
    )

    async def mock_acompletion(*args, **kwargs):
        return {"success": True, "text": json.dumps(mismatch_json)}

    with patch("core.llm.llm_gateway.llm_gateway.acompletion", new=mock_acompletion):
        creator = AutoSkillCreator()
        result = await creator.generate_and_deploy_skill(
            user_demand="Analyze reviews sentiment", skill_name="SentimentAnalyzer"
        )

        assert result["success"] is False
        assert "Validation test 1 failed" in result["error"]

        # Ensure not saved in dynamic folder
        # registry.get_skill("SentimentAnalyzer") now returns a dict by default, so we just check it isn't in DB or dir
        assert not (loader.skills_dir / "SentimentAnalyzer").exists()


@pytest.mark.anyio
async def test_pipeline_invalid_uss_pydantic(clean_dynamic_skills, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_SANDBOX_FALLBACK", "true")
    _loader, _registry, _installer = clean_dynamic_skills

    # Invalid semver version format inside metadata
    bad_uss_json = MOCK_AI_RESPONSE_JSON.copy()
    bad_uss_json["schema"] = bad_uss_json["schema"].copy()
    bad_uss_json["schema"]["metadata"] = bad_uss_json["schema"]["metadata"].copy()
    bad_uss_json["schema"]["metadata"]["version"] = "1.0"

    async def mock_acompletion(*args, **kwargs):
        return {"success": True, "text": json.dumps(bad_uss_json)}

    with patch("core.llm.llm_gateway.llm_gateway.acompletion", new=mock_acompletion):
        creator = AutoSkillCreator()
        result = await creator.generate_and_deploy_skill(
            user_demand="Analyze reviews sentiment", skill_name="SentimentAnalyzer"
        )

        assert result["success"] is False
        assert "USS Validation Exception" in result["error"]
