from baseline_commands import validate_registry


def test_baseline_registry_is_valid():
    assert validate_registry() == []
