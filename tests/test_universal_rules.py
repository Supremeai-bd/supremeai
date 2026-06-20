import os
import tempfile
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
