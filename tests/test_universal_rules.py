import json
import os
from core.universal_rules import UniversalRulesEngine


def test_default_rules_loaded():
    engine = UniversalRulesEngine()
    assert 'directions' in engine.rules
    assert 'image_generation' in engine.rules
    assert 'cost_management' in engine.rules


def test_save_rules_atomic_write(tmp_path):
    rules_path = os.path.join(tmp_path, 'test_rules.json')
    engine = UniversalRulesEngine(rules_path=rules_path)
    new_rules = {'test': True, 'value': 42}
    assert engine.save_rules(new_rules) is True
    with open(rules_path, 'r', encoding='utf-8') as f:
        saved = json.load(f)
    assert saved == new_rules


def test_apply_direction_rules():
    engine = UniversalRulesEngine()
    ctx = {'direction': 'North', 'cost': 0.005}
    result = engine.apply(ctx)
    assert result['direction_count'] == 5
    assert result['direction_names'] == ['North', 'South', 'East', 'West', 'Center']


def test_apply_cost_block():
    engine = UniversalRulesEngine()
    ctx = {'cost': 10.0, 'task_type': 'image_generation'}
    result = engine.apply(ctx)
    assert result.get('blocked') is True
    assert 'Max cost' in result.get('reason', '')
