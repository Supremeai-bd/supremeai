from core.effective_policy import ConfigurablePolicyStore


def test_user_rules_override_admin_values_without_changing_features():
    store = ConfigurablePolicyStore()
    store.update_admin({"task_mode": "approval_first"}, {"browser_tasks": True})
    policy = store.update_user("user-1", {"task_mode": "draft_only"})

    assert policy.rules["task_mode"] == "draft_only"
    assert policy.sources["task_mode"] == "user"
    assert policy.features["browser_tasks"] is True


def test_user_policy_isolated_between_users():
    store = ConfigurablePolicyStore()
    store.update_user("user-1", {"allow_submissions": False})

    assert store.snapshot("user-1").rules["allow_submissions"] is False
    assert store.snapshot("user-2").rules["allow_submissions"] is True


def test_admin_can_disable_feature_for_all_users():
    store = ConfigurablePolicyStore()
    store.update_admin(features={"browser_tasks": False})

    assert store.snapshot("user-1").features["browser_tasks"] is False
