"""Issue #1669 (CRITICAL) — render proxy ticket-based auth tests.

Old state: `MobileSimulator` embedded `?token=<JWT>` into the iframe URL for
`GET /api/browser/render` — but the route lived on the header-authenticated
router, so the query token was NEVER verified (pure leak into browser history,
access logs, Referer headers) and the iframe could never authenticate anyway.

New contract:
1. `POST /api/browser/render-ticket` (header-authed router) issues a one-time,
   60s-TTL crypto-random ticket
2. `GET /api/browser/render` lives on a dependency-free router and REQUIRES a
   valid unconsumed ticket — no/invalid/reused/expired → 401 (fail-closed)
3. SSRF hardening and framing (P6) headers are unchanged
"""

import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.routes.browser import _render_proxy
from api.routes.browser._render_proxy import (
    _consume_ticket,
    _issue_ticket,
    render_proxy,
)


class TestTicketLifecycle:
    def test_issue_ticket_is_random_and_unconsumed(self):
        t1 = _issue_ticket()
        t2 = _issue_ticket()
        assert t1 != t2
        assert len(t1) >= 32  # token_urlsafe(32)
        assert _consume_ticket(t1) is True

    def test_consume_is_one_time_only(self):
        t = _issue_ticket()
        assert _consume_ticket(t) is True
        assert _consume_ticket(t) is False  # reuse denied

    def test_expired_ticket_fails(self):
        t = _issue_ticket()
        with patch.object(_render_proxy.time, "time", return_value=time.time() + 3600):
            assert _consume_ticket(t) is False

    def test_missing_ticket_fails(self):
        assert _consume_ticket(None) is False
        assert _consume_ticket("") is False


class TestRenderProxyAuth:
    def test_render_without_ticket_401(self):
        with pytest.raises(HTTPException) as exc:
            render_proxy(url="https://example.com", ticket="")
        assert exc.value.status_code == 401

    def test_render_with_invalid_ticket_401(self):
        with pytest.raises(HTTPException) as exc:
            render_proxy(url="https://example.com", ticket="not-a-real-ticket")
        assert exc.value.status_code == 401

    def test_render_with_reused_ticket_401_after_first_success(self):
        t = _issue_ticket()
        with patch.object(_render_proxy.urllib.request, "urlopen") as urlopen_mock:
            ctx = urlopen_mock.return_value.__enter__.return_value
            ctx.headers = {"Content-Type": "text/html"}
            ctx.read.side_effect = [b"<html><head></head><body>ok</body></html>", b""]
            resp = render_proxy(url="https://example.com", ticket=t)
            assert resp.status_code == 200
        # second use of the SAME ticket → 401 (single-use enforced)
        with pytest.raises(HTTPException) as exc:
            render_proxy(url="https://example.com", ticket=t)
        assert exc.value.status_code == 401

    def test_render_with_valid_ticket_returns_proxied_html(self):
        t = _issue_ticket()
        with patch.object(_render_proxy.urllib.request, "urlopen") as urlopen_mock:
            ctx = urlopen_mock.return_value.__enter__.return_value
            ctx.headers = {"Content-Type": "text/html; charset=utf-8"}
            ctx.read.side_effect = [b"<html><head></head><body>hello</body></html>", b""]
            resp = render_proxy(url="https://example.com", ticket=t)
        assert resp.status_code == 200
        # framing contract (P6) preserved
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert "frame-ancestors" in resp.headers.get("Content-Security-Policy", "")
        assert "*" not in resp.headers.get("Content-Security-Policy", "")

    def test_render_ticket_gates_blocked_hosts_too(self):
        t = _issue_ticket()
        # ticket consumed, but SSRF guard still applies to the URL
        with pytest.raises(HTTPException) as exc:
            render_proxy(url="http://127.0.0.1:8080/secret", ticket=t)
        assert exc.value.status_code == 400
