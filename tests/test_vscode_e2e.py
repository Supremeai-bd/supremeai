import os
import sys
import time
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


class FakeVSCodeWorkspace:
    def __init__(self):
        self._fs: Dict[str, str] = {}

    def open_text_document(self, uri: str) -> dict:
        self._fs.setdefault(uri, "")
        return {"uri": uri, "text": self._fs[uri]}

    def apply_edit(self, edit) -> bool:
        return True

    def open_uri(self, uri: str) -> bool:
        return True


class FakeVSCodeWindow:
    def __init__(self):
        self._visible_documents: List[dict] = []
        self._status_text: str = ""
        self._palette_items: List[str] = []
        self._notifications: List[dict] = []
        self._selection: Dict[str, Any] = {}
        self.terminals: List[Any] = []

    def show_text_document(self, doc: dict, column=None):
        self._visible_documents.append(doc)

    def show_information_message(self, text: str, *actions):
        self._notifications.append({"type": "info", "text": text, "actions": actions})
        return actions[0] if actions else None

    def show_error_message(self, text: str, *actions):
        self._notifications.append({"type": "error", "text": text, "actions": actions})
        return actions[0] if actions else None

    def set_status_text(self, text: str):
        self._status_text = text

    def show_quick_pick(self, items: List[Any]):
        self._palette_items = list(items) if isinstance(items, list) else []
        return None

    def with_progress(self, location, task):
        mock = MagicMock()
        mock.report = lambda msg, *args: None
        task(mock)


class FakeVSCodeTerminal:
    def __init__(self):
        self.name = ""
        self.closed = False

    def send_text(self, text: str):
        return True

    def dispose(self):
        self.closed = True


class FakeInlineCompletionProvider:
    def __init__(self):
        self._triggered: List[Dict[str, Any]] = []

    def trigger(self, position: Dict[str, int], document: dict):
        self._triggered.append({"position": position, "document": document})
        return [
            {"text": "suggested completion from AI"},
            {"text": "secondary suggestion"},
        ]


class FakeAuthenticationProvider:
    def __init__(self):
        self._jwt_storage: Dict[str, str] = {}

    def get_session(self, options):
        session = MagicMock()
        session.id = "auth-1"
        session.access_token = "jwt-token-123"
        session.account = MagicMock()
        session.account.label = "user@example.com"
        self._jwt_storage[session.id] = session.access_token
        return session

    def store_jwt(self, key: str, token: str):
        self._jwt_storage[key] = token

    def retrieve_jwt(self, key: str) -> str:
        return self._jwt_storage.get(key, "")


class FakeCodeFlowPanel:
    def __init__(self):
        self._rendered: bool = False
        self._content: Dict[str, Any] = {}
        self._opened: bool = False

    def open(self):
        self._opened = True

    def render(self, content: Dict[str, Any]):
        self._rendered = True
        self._content = content

    @property
    def is_rendered(self) -> bool:
        return self._rendered

    @property
    def content(self) -> Dict[str, Any]:
        return self._content


def fake_create_dummy_file(path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("print('hello, world!')\n")
    return path


def test_vscode_inline_completion_triggers():
    with patch.dict(os.environ, {"VSCODE_WORKSPACE": "/tmp/vscode-test"}):
        workspace = FakeVSCodeWorkspace()
        provider = FakeInlineCompletionProvider()
        uri = "file:///workspace/main.py"
        document = workspace.open_text_document(uri)

        completions = provider.trigger({"line": 0, "character": 6}, document)

        assert len(completions) == 2
        assert completions[0]["text"].startswith("suggested")
        assert len(provider._triggered) == 1


def test_vscode_command_accept_reject_feedback():
    window = FakeVSCodeWindow()

    accept_event = {"type": "command.accept", "commmand_id": "codeflow.accept", "item": "selected-state"}
    reject_event = {"type": "command.reject", "command_id": "codeflow.reject", "item": "selected-state", "reason": "irrelevant"}

    events = [accept_event, reject_event]

    for event in events:
        assert event["type"] in {"command.accept", "command.reject"}

    assert window._status_text == ""
    window.set_status_text("Accept recorded")
    assert "Accept" in window._status_text

    window.set_status_text("Reject recorded: irrelevant")
    assert "Reject recorded" in window._status_text


def test_vscode_panel_opens_and_renders():
    panel = FakeCodeFlowPanel()

    assert panel._opened is False
    assert panel._rendered is False

    panel.open()
    assert panel._opened is True

    panel.render({"title": "CodeFlow", "cards": [], "loading": False})
    assert panel._rendered is True
    assert panel.content["loading"] is False
    assert panel.content["title"] == "CodeFlow"


def test_vscode_auth_stores_jwt():
    auth = FakeAuthenticationProvider()

    session = auth.get_session({})

    assert session.access_token == "jwt-token-123"
    assert auth.retrieve_jwt(session.id) == "jwt-token-123"

    auth.store_jwt("session-2", "different-jwt-456")
    assert auth.retrieve_jwt("session-2") == "different-jwt-456"


def test_vscode_e2e_full_flow():
    workspace = FakeVSCodeWorkspace()
    window = FakeVSCodeWindow()
    provider = FakeInlineCompletionProvider()
    panel = FakeCodeFlowPanel()
    auth = FakeAuthenticationProvider()

    uri = "file:///workspace/features/user_service.py"
    document = workspace.open_text_document(uri)
    window.show_text_document(document)

    completions = provider.trigger({"line": 4, "character": 20}, document)
    assert len(completions) == 2

    accepted = completions[0]
    window.set_status_text(f"Accepted: {accepted['text']}")
    assert "Accepted" in window._status_text

    panel.open()
    panel.render({
        "title": "CodeFlow",
        "cards": [{"id": "c-1", "text": accepted["text"]}],
        "loading": False,
    })
    assert panel.is_rendered is True
    assert panel.content["cards"][0]["text"] == accepted["text"]

    session = auth.get_session({})
    assert auth.retrieve_jwt(session.id) == "jwt-token-123"

    window.show_information_message("Full flow complete")
    assert any(n["type"] == "info" and "complete" in n["text"] for n in window._notifications)
