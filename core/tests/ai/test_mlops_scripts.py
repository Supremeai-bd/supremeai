"""Unit and integration tests for MLOps scripts (bias_detector, model_drift_detector, prompt_injection_tester, model_version_manager)."""

import importlib.util
import os
import tempfile
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

repo_root = Path(__file__).resolve().parents[3]


def _import_script(relative_path: str, module_name: str):
    file_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bias_mod = _import_script("scripts/ai/bias_detector.py", "bias_detector")
drift_mod = _import_script("scripts/ai/model_drift_detector.py", "model_drift_detector")
injection_mod = _import_script("scripts/ai/prompt_injection_tester.py", "prompt_injection_tester")
version_mod = _import_script("scripts/ai/model_version_manager.py", "model_version_manager")

BiasDetector = bias_mod.BiasDetector
ModelDriftDetector = drift_mod.ModelDriftDetector
PromptInjectionTester = injection_mod.PromptInjectionTester
ModelVersionManager = version_mod.ModelVersionManager
ModelStatus = version_mod.ModelStatus


class TestBiasDetector:
    def test_detect_bias_sanity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = BiasDetector(output_path=tmpdir)
            predictions = np.array([0.9, 0.8, 0.2, 0.1])
            protected = {
                "gender_male": np.array([1, 1, 0, 0]),
            }
            result = detector.detect_bias(
                model_id="unit-test-model",
                predictions=predictions,
                protected_attributes=protected,
                text_samples=["test prompt male", "test prompt female"],
            )
            assert result.model_id == "unit-test-model"
            assert result.overall_fairness_score >= 0.0
            report_path = detector.generate_report(result)
            assert os.path.exists(report_path)


class TestModelDriftDetector:
    def test_drift_detection_workflow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_drift.db")
            detector = ModelDriftDetector(db_path=db_path)
            features = np.random.randn(100, 5)
            preds = np.random.randn(100)

            detector.save_baseline("test-model", features, preds)
            results = detector.run_full_drift_check(
                "test-model", features, preds, current_accuracy=0.90
            )
            assert len(results) >= 1


class TestPromptInjectionTester:
    @pytest.mark.asyncio
    async def test_comprehensive_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tester = PromptInjectionTester(output_path=tmpdir)
            results = await tester.run_comprehensive_test()
            assert len(results) >= 1
            summary = tester.get_summary()
            assert "total_tests" in summary


class TestModelVersionManager:
    def test_version_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "registry.db")
            storage_path = os.path.join(tmpdir, "storage")
            artifacts_dir = os.path.join(tmpdir, "artifacts")
            os.makedirs(artifacts_dir, exist_ok=True)
            Path(artifacts_dir, "model.bin").write_text("dummy model weights", encoding="utf-8")

            manager = ModelVersionManager(storage_path=storage_path, db_path=db_path)
            version = manager.create_version(
                model_name="demo-llm",
                version_number="1.0.0",
                artifacts_path=artifacts_dir,
                metrics={"accuracy": 0.95},
            )
            assert version.version_number == "1.0.0"
            assert version.status == ModelStatus.STAGING

            promoted = manager.promote_to_production(version.version_id)
            assert promoted is True
