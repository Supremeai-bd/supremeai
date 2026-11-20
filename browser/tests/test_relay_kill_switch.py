"""One dead engine must be switchable off at 3am, not at the next deploy.

Before this, the only levers were "wait for a cooldown the gateway inferred" and
"change an env var and redeploy". The relay is the half that actually chooses an
engine, so the switch is enforced there and published on the endpoints the
gateway already reads.

What is pinned:

* the switch is enforced at dispatch on **both** paths (JSON and SSE), not just
  reported;
* switching everything off is a 503 / an `operator_disabled` frame — not a 502,
  because nothing upstream failed and the gateway must not read it as an injury;
* the choice is reversible, and re-enabling restores service immediately;
* `/health`, `/models` and `/admin/engines` agree about the state, and the admin
  route is behind the same secret every other operator route uses.
"""


from fastapi.testclient import TestClient
import pytest

import server  # noqa: E402

BODY = {"messages": [{"role": "user", "content": "hi"}], "model": "duck-claude"}


@pytest.fixture(autouse=True)
def _clean_switches():
    server._engine_disabled.clear()
    saved = dict(server._engine_latency)
    server._engine_latency.clear()
    yield
    server._engine_disabled.clear()
    server._engine_latency.clear()
    server._engine_latency.update(saved)


def _engines(*parts):
    async def gen(*_a, **_k):
        for part in parts:
            yield part

    return gen


def _answer(text):
    async def ask(*_a, **_k):
        return text

    return ask


def _frames(body):
    return [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]


# --- the switch itself -----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("duck", {"duck"}),
        ("gemini-web", {"gemini"}),          # the published id is accepted
        ("duck:quota burn,gemini", {"duck", "gemini"}),
        (" duck , ", {"duck"}),
        ("duck,unobtainium", {"duck"}),      # unknown names are ignored, not obeyed
        ("", set()),
    ],
)
def test_env_seeding_accepts_both_spellings_and_ignores_nonsense(raw, expected):
    assert set(server._seed_disabled_engines(raw)) == expected


def test_the_reason_from_the_env_is_kept():
    seeded = server._seed_disabled_engines("duck:returning garbage")
    assert seeded["duck"]["reason"] == "returning garbage"


def test_an_unknown_engine_is_a_404_not_a_silent_no_op():
    with pytest.raises(Exception) as excinfo:
        server.set_engine_disabled("unobtainium", True)
    assert getattr(excinfo.value, "status_code", None) == 404


def test_disabling_and_enabling_are_symmetric():
    client = TestClient(server.app)
    assert client.post("/admin/engines", json={"engine": "duck", "disabled": True}).json()["disabled"]
    assert server.engine_disabled("duck")

    assert not client.post("/admin/engines", json={"engine": "duck", "disabled": False}).json()["disabled"]
    assert not server.engine_disabled("duck")


def test_the_admin_route_rejects_a_bad_body():
    client = TestClient(server.app)
    assert client.post("/admin/engines", json={"engine": "duck"}).status_code == 400
    assert client.post("/admin/engines", json={"engine": "duck", "disabled": "yes"}).status_code == 400
    assert client.post("/admin/engines", content=b"not json").status_code == 400


def test_the_admin_route_uses_the_same_secret_as_every_operator_route(monkeypatch):
    monkeypatch.setenv("STEALTH_WEBHOOK_SECRET", "switch-token")
    client = TestClient(server.app)

    assert client.get("/admin/engines").status_code == 401
    assert client.post("/admin/engines", json={"engine": "duck", "disabled": True}).status_code == 401

    ok = client.post(
        "/admin/engines",
        json={"engine": "duck", "disabled": True},
        headers={"X-Stealth-Secret": "switch-token"},
    )
    assert ok.status_code == 200 and ok.json()["disabled"] is True


# --- enforcement -----------------------------------------------------------


def test_a_disabled_engine_is_never_dispatched_to(monkeypatch):
    calls = []

    async def duck(*_a, **_k):
        calls.append("duck")
        yield "duck answer"

    monkeypatch.setattr(server.duck_engine, "ask_stream", duck)
    monkeypatch.setattr(server.relay_engine, "ask", _answer("gemini answer"))
    server.set_engine_disabled("duck", True, "test")

    body = TestClient(server.app).post("/v1/chat/completions", json=BODY).json()

    assert calls == [], "the relay chose a switched-off engine"
    assert body["choices"][0]["message"]["content"] == "gemini answer"


def test_everything_switched_off_is_a_503_not_an_injury(monkeypatch):
    """503 says "operator", 502 says "upstream broke" — the gateway only cools on the second."""
    monkeypatch.setattr(
        server.duck_engine, "ask_stream", _engines("should not run")
    )
    server.set_engine_disabled("duck", True)
    server.set_engine_disabled("gemini", True)

    resp = TestClient(server.app).post("/v1/chat/completions", json=BODY)

    assert resp.status_code == 503
    assert "switched off" in resp.json()["detail"]


def test_everything_switched_off_streams_an_operator_frame(monkeypatch):
    server.set_engine_disabled("duck", True)
    server.set_engine_disabled("gemini", True)

    resp = TestClient(server.app).post("/v1/chat/completions", json=BODY | {"stream": True})
    frames = _frames(resp.text)

    assert resp.status_code == 200
    assert frames[-1] == "[DONE]"
    assert '"operator_disabled"' in frames[0]


def test_re_enabling_restores_service_without_a_restart(monkeypatch):
    monkeypatch.setattr(server.duck_engine, "ask_stream", _engines("back online"))
    monkeypatch.setattr(server.relay_engine, "ask", _answer("gemini"))
    # Both off first, so the "after" request can only be served by a duck that
    # was genuinely re-enabled — not by the other engine winning on latency.
    server.set_engine_disabled("duck", True)
    server.set_engine_disabled("gemini", True)

    before = TestClient(server.app).post("/v1/chat/completions", json=BODY)
    server.set_engine_disabled("duck", False)
    after = TestClient(server.app).post("/v1/chat/completions", json=BODY).json()

    assert before.status_code == 503
    assert after["choices"][0]["message"]["content"] == "back online"


# --- publication -----------------------------------------------------------


def test_health_publishes_the_switch_with_a_reason():
    server.set_engine_disabled("gemini", True, "cookie burn")
    sessions = TestClient(server.app).get("/health").json()["sessions"]

    assert sessions["gemini-web"]["disabled"] is True
    assert sessions["gemini-web"]["disabled_reason"] == "cookie burn"
    assert sessions["duck"]["disabled"] is False


def test_models_keeps_the_row_and_marks_it_disabled():
    """Removing the row would make the gateway's engine join miss the id entirely."""
    server.set_engine_disabled("gemini", True)
    rows = {row["id"]: row for row in TestClient(server.app).get("/models").json()["data"]}

    assert set(rows) == {"duck", "gemini-web"}
    assert rows["gemini-web"]["disabled"] is True
    assert rows["duck"]["disabled"] is False


def test_the_admin_view_matches_the_health_view():
    server.set_engine_disabled("duck", True, "why not")
    listed = TestClient(server.app).get("/admin/engines").json()["engines"]
    by_published = {row["published_id"]: row for row in listed}

    assert by_published["duck"]["disabled"] is True
    assert by_published["duck"]["reason"] == "why not"
    assert by_published["gemini-web"]["disabled"] is False
