from core.intent_router import IntentRouter


def test_intent_router_no_keywords_defaults_to_chat():
    r = IntentRouter()
    action = r.route("hello there")
    assert action.action_type == "chat"
    assert action.target_module is None
    assert action.confidence == 0.5


def test_intent_router_code_generate():
    r = IntentRouter()
    action = r.route("please write python function")
    assert action.action_type == "code_generate"
    assert action.target_module == "ide"
    assert action.label == "Generate Code"
    assert action.payload["language"] == "python"
    assert action.payload["filename"] == "main.py"


def test_intent_router_deploy_firebase_precedence():
    r = IntentRouter()
    action = r.route("deploy to firebase")
    assert action.action_type == "deploy"
    assert action.payload["target"] == "firebase"


def test_intent_router_video_edit_requires_confirmation():
    r = IntentRouter()
    action = r.route("edit video trim clip")
    assert action.action_type == "video_edit"
    assert action.requires_confirmation is True
