import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from core.universal_rules import UniversalRulesEngine


def test_load_default_rules():
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = os.path.join(tmpdir, "admin_rules.json")
        engine = UniversalRulesEngine(rules_path=rules_path)

        assert os.path.exists(rules_path)
        assert engine.rules["directions"]["count"] == 5
        assert engine.rules["cost_management"]["monthly_budget"] == 30.00


def test_save_rules():
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = os.path.join(tmpdir, "admin_rules.json")
        engine = UniversalRulesEngine(rules_path=rules_path)

        new_rules = engine.rules.copy()
        new_rules["cost_management"]["monthly_budget"] = 50.00

        assert engine.save_rules(new_rules)

        engine2 = UniversalRulesEngine(rules_path=rules_path)
        assert engine2.rules["cost_management"]["monthly_budget"] == 50.00


def test_apply_rules():
    engine = UniversalRulesEngine()

    context = {"direction": "North"}
    modified = engine.apply(context)
    assert modified["direction_count"] == 5
    assert modified["direction_override_applied"] is True

    context_cost_ok = {"task_type": "image_generation", "cost": 0.005}
    modified_ok = engine.apply(context_cost_ok)
    assert "blocked" not in modified_ok

    context_cost_bad = {"task_type": "image_generation", "cost": 0.02}
    modified_bad = engine.apply(context_cost_bad)
    assert modified_bad["blocked"] is True
    assert "Exceeds Universal Rule" in modified_bad["reason"]


def test_apply_rules_directions_plural_key():
    engine = UniversalRulesEngine()
    context = {"directions": ["North", "South"]}
    modified = engine.apply(context)
    assert modified["direction_count"] == 5
    assert modified["direction_override_applied"] is True


def test_apply_rules_no_direction_no_modification():
    engine = UniversalRulesEngine()
    context = {"task_type": "general"}
    modified = engine.apply(context)
    assert "direction_count" not in modified
    assert "direction_override_applied" not in modified


def test_apply_rules_non_image_generation_not_blocked():
    engine = UniversalRulesEngine()
    context = {"task_type": "coding", "cost": 100.0}
    modified = engine.apply(context)
    assert "blocked" not in modified


def test_apply_rules_no_cost_field_not_blocked():
    engine = UniversalRulesEngine()
    context = {"task_type": "image_generation"}
    modified = engine.apply(context)
    assert "blocked" not in modified


def test_load_rules_from_existing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = os.path.join(tmpdir, "admin_rules.json")
        custom = {"directions": {"count": 3, "names": ["A", "B", "C"], "description": "test"}}
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(custom, f)
        engine = UniversalRulesEngine(rules_path=rules_path)
        assert engine.rules["directions"]["count"] == 3
        assert engine.rules["directions"]["names"] == ["A", "B", "C"]


def test_load_rules_corrupted_file_falls_back_to_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = os.path.join(tmpdir, "admin_rules.json")
        with open(rules_path, "w", encoding="utf-8") as f:
            f.write("NOT VALID JSON{{{")
        engine = UniversalRulesEngine(rules_path=rules_path)
        assert engine.rules["directions"]["count"] == 5


def test_save_rules_creates_parent_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = os.path.join(tmpdir, "sub", "dir", "admin_rules.json")
        engine = UniversalRulesEngine(rules_path=rules_path)
        assert engine.save_rules(engine.rules)
        assert os.path.exists(rules_path)


def test_save_rules_atomic_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = os.path.join(tmpdir, "admin_rules.json")
        engine = UniversalRulesEngine(rules_path=rules_path)
        new_rules = engine.rules.copy()
        new_rules["cost_management"]["monthly_budget"] = 99.99
        engine.save_rules(new_rules)
        with open(rules_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["cost_management"]["monthly_budget"] == 99.99


def test_default_rules_path_is_project_data_dir():
    engine = UniversalRulesEngine()
    expected = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "admin_rules.json",
    )
    assert engine.rules_path == expected


def test_save_rules_returns_false_on_io_error():
    import os as _os
    engine = UniversalRulesEngine()
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = _os.path.join(tmpdir, "admin_rules.json")
        engine.rules_path = rules_path
        with patch.object(_os, "replace", side_effect=OSError("permission denied")):
            result = engine.save_rules({"test": "value"})
        assert result is False


def test_apply_rules_exact_cost_boundary():
    engine = UniversalRulesEngine()
    max_cost = engine.rules["image_generation"]["max_cost_per_image"]
    context_ok = {"task_type": "image_generation", "cost": max_cost}
    modified_ok = engine.apply(context_ok)
    assert "blocked" not in modified_ok
    context_over = {"task_type": "image_generation", "cost": max_cost + 0.001}
    modified_over = engine.apply(context_over)
    assert modified_over["blocked"] is True


def test_apply_rules_preserves_other_context_keys():
    engine = UniversalRulesEngine()
    context = {"direction": "North", "custom_key": "custom_value", "cost": 0.005}
    modified = engine.apply(context)
    assert modified["custom_key"] == "custom_value"
    assert "direction_count" in modified
