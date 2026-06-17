import os
import sys
import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


class FakeFlutterProject:
    def __init__(self):
        self._routes: List[str] = []
        self._pages: Dict[str, Dict[str, Any]] = {}

    def push(self, route: str, data: Dict[str, Any]):
        self._routes.append(route)
        self._pages[route] = data

    @property
    def current_route(self) -> str:
        return self._routes[-1] if self._routes else ""

    @property
    def route_history(self) -> List[str]:
        return list(self._routes)


class FakeChatGateway:
    def __init__(self):
        self._connected: bool = False
        self._messages: List[str] = []

    def connect(self):
        self._connected = True

    def send(self, message: str):
        if not self._connected:
            raise RuntimeError("ChatGateway not connected")
        self._messages.append(message)
        return "ack"

    def disconnect(self):
        self._connected = False


class FakeNotificationService:
    def __init__(self):
        self._announcements: List[str] = []
        self._rendered: bool = False

    def show_new(self, announcement: str):
        self._announcements.append(announcement)

    def render(self):
        self._rendered = True

    @property
    def latest(self) -> str:
        return self._announcements[-1] if self._announcements else ""


class FakeMobileChart:
    def __init__(self):
        self._points: List[Dict[str, Any]] = []

    def load_data(self, points: List[Dict[str, Any]]):
        self._points = list(points)

    @property
    def points(self) -> List[Dict[str, Any]]:
        return list(self._points)


class FakeAuthGateway:
    VALID_TOKEN = "Bearer eyJhbGciOiJIUzI1NiJ9.dummy-jwt-payload.signature"

    def authenticate(self, email: str, password: str):
        if email == "user@example.com" and password == "password":
            return {"token": self.VALID_TOKEN, "user": {"email": email}}
        return {"token": None, "error": "invalid_credentials"}

    def validate(self, authorization: str):
        if authorization == self.VALID_TOKEN:
            return {"valid": True}
        return {"valid": False, "error": "unauthorized"}


class FakeProjectAPI:
    def __init__(self, projects: List[Dict[str, Any]]):
        self._projects = list(projects)

    def fetch_projects(self, user_id: str) -> List[Dict[str, Any]]:
        return self._projects


FAKE_DASHBOARD_WIDGETS = [
    {"type": "kpi", "title": "Tasks Completed", "value": 42},
    {"type": "chart", "title": "Productivity", "points": [{"x": 1, "y": 10}, {"x": 2, "y": 15}]},
]

FAKE_PROJECTS = [
    {"id": "p-1", "name": "Alpha", "status": "active"},
    {"id": "p-2", "name": "Beta", "status": "archived"},
]


def test_mobile_dashboard_loads():
    project = FakeFlutterProject()
    chart = FakeMobileChart()
    project.push("/dashboard", {"widgets": FAKE_DASHBOARD_WIDGETS, "chart": chart})
    assert project.current_route == "/dashboard"
    page = project.route_history[-1]
    assert page == "/dashboard"

    data = project.pages[page]
    assert len(data["widgets"]) == 2
    assert data["widgets"][0]["type"] == "kpi"
    assert data["widgets"][0]["value"] == 42


def test_mobile_project_list_fetches():
    api = FakeProjectAPI(FAKE_PROJECTS)
    project = FakeFlutterProject()

    projects = api.fetch_projects(user_id="u-1")
    assert len(projects) == 2
    assert projects[0]["id"] == "p-1"
    assert projects[0]["status"] == "active"

    project.push("/projects", {"projects": projects, "user_id": "u-1"})
    assert project.current_route == "/projects"
    assert project.pages["/projects"]["projects"][1]["name"] == "Beta"


def test_mobile_chat_gateway_connects():
    gateway = FakeChatGateway()
    project = FakeFlutterProject()

    gateway.connect()
    assert gateway._connected is True

    ack = gateway.send("Hello from mobile")
    assert ack == "ack"
    assert gateway._messages == ["Hello from mobile"]

    project.push("/chat", {"gateway": "connected", "message_count": 1})
    assert project.current_route == "/chat"

    gateway.disconnect()
    assert gateway._connected is False


def test_mobile_notifications_screen_renders():
    service = FakeNotificationService()
    project = FakeFlutterProject()

    service.show_new("Build completed successfully")
    service.show_new("Deployment to staging started")
    assert service.latest == "Deployment to staging started"

    service.render()
    assert service._rendered is True

    project.push("/notifications", {"items": service._announcements})
    assert project.current_route == "/notifications"
    assert len(project.pages["/notifications"]["items"]) == 2


def test_mobile_auth_stores_token_on_login():
    auth = FakeAuthGateway()
    project = FakeFlutterProject()

    result = auth.authenticate("user@example.com", "password")
    assert result["token"] == FakeAuthGateway.VALID_TOKEN

    project.push("/home", {"token": result["token"], "user": result["user"]})
    assert project.current_route == "/home"
    assert project.pages["/home"]["token"] == FakeAuthGateway.VALID_TOKEN

    validation = auth.validate(project.pages["/home"]["token"])
    assert validation["valid"] is True

    invalid = auth.validate("Bearer bad-token")
    assert invalid["valid"] is False


def test_mobile_e2e_full_flow():
    auth = FakeAuthGateway()
    api = FakeProjectAPI(FAKE_PROJECTS)
    gateway = FakeChatGateway()
    notifications = FakeNotificationService()
    project = FakeFlutterProject()

    # Auth
    login_result = auth.authenticate("user@example.com", "password")
    assert login_result["token"] == FakeAuthGateway.VALID_TOKEN
    project.push("/home", {"token": login_result["token"], "user": login_result["user"]})

    # Dashboard
    project.push("/dashboard", {"widgets": FAKE_DASHBOARD_WIDGETS})
    assert project.current_route == "/dashboard"

    # Project list
    projects = api.fetch_projects(user_id="u-1")
    project.push("/projects", {"projects": projects})
    assert project.current_route == "/projects"
    assert len(project.pages["/projects"]["projects"]) == 2

    # Chat
    gateway.connect()
    gateway.send("First message")
    project.push("/chat", {"message_count": 1})
    assert project.current_route == "/chat"

    # Notifications
    notifications.show_new("Chat agent responded")
    notifications.render()
    project.push("/notifications", {"items": notifications._announcements})
    assert project.current_route == "/notifications"
    assert notifications.latest == "Chat agent responded"
