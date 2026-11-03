from unittest.mock import MagicMock, patch

import httpx

from services.scraper.web_scraper import WebScraper


def test_fetch_page_blocks_ssrf():
    scraper = WebScraper()
    with patch("services.scraper.web_scraper.is_safe_url", return_value=False):
        result = scraper.fetch_page("http://127.0.0.1:8080/secret")  # is_local()
    assert result["success"] is False
    assert "SSRF" in result["error"]
    assert result["url"] == "http://127.0.0.1:8080/secret"  # is_local()


def test_fetch_page_blocks_unsafe_resolved_ip():
    """Issue #511: the resolved-IP gate must run before the first request."""
    with (
        patch("services.scraper.web_scraper.is_safe_url", return_value=True),
        patch("services.scraper.web_scraper.is_safe_url_resolved", return_value=False),
        patch("services.scraper.web_scraper.httpx.get") as mock_get,
    ):
        result = WebScraper().fetch_page("http://rebinding.example/")

    assert result["success"] is False
    assert "SSRF" in result["error"]
    mock_get.assert_not_called()


def test_fetch_page_blocks_redirect_to_internal_target():
    """Issue #511: redirects are followed manually and re-validated per hop."""
    redirect_calls = []

    class RedirectResponse:
        status_code = 302
        headers = {"location": "http://169.254.169.254/latest/meta-data/"}
        text = ""

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, **kwargs):
        redirect_calls.append(url)
        return RedirectResponse()

    with (
        patch(
            "services.scraper.web_scraper.is_safe_url",
            side_effect=lambda u: "169.254" not in u,
        ),
        patch("services.scraper.web_scraper.is_safe_url_resolved", return_value=True),
        patch("services.scraper.web_scraper.httpx.get", side_effect=fake_get),
    ):
        result = WebScraper().fetch_page("http://attacker.example/redir")

    assert result["success"] is False
    assert "SSRF" in result["error"]
    assert redirect_calls == ["http://attacker.example/redir"]  # metadata hop never requested


def test_fetch_page_parses_html_successfully():
    class _FakeResponse:
        status_code = 200
        text = (
            "<html><head><title>Hello Title</title></head>"
            "<body><script>ignore()</script><p>Main content here</p>"
            "<a href='/page-a'>A</a><a href='/page-b'>B</a></body></html>"
        )

        def raise_for_status(self):
            return None

    with (
        patch("services.scraper.web_scraper.is_safe_url", return_value=True),
        patch("services.scraper.web_scraper.is_safe_url_resolved", return_value=True),
        patch("services.scraper.web_scraper.httpx.get", return_value=_FakeResponse()),
    ):
        result = WebScraper().fetch_page("https://example.com")

    assert result["success"] is True
    assert result["title"] == "Hello Title"
    assert "Main content here" in result["content"]
    assert result["links"] == ["/page-a", "/page-b"]
    assert result["status_code"] == 200


def test_fetch_page_handles_request_error():
    with (
        patch("services.scraper.web_scraper.is_safe_url", return_value=True),
        patch("services.scraper.web_scraper.is_safe_url_resolved", return_value=True),
        patch(
            "services.scraper.web_scraper.httpx.get",
            side_effect=httpx.RequestError("connection refused"),
        ),
    ):
        result = WebScraper().fetch_page("https://example.com")

    assert result["success"] is False
    assert "connection refused" in result["error"]
