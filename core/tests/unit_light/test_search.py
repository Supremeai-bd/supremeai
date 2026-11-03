from unittest.mock import MagicMock, patch

from core.search import web_search


def test_web_search_returns_empty_when_client_unavailable():
    with patch("core.search._ddgs_client", return_value=None):
        assert web_search("python") == []


def test_web_search_returns_results_from_client():
    fake = MagicMock()
    fake.text.return_value = [{"title": "a", "href": "b", "body": "c"}]
    with patch("core.search._ddgs_client", return_value=fake):
        result = web_search("python", max_results=3)
    assert result == [{"title": "a", "href": "b", "body": "c"}]
    fake.text.assert_called_once_with("python", max_results=3)


def test_web_search_returns_empty_on_client_error():
    fake = MagicMock()
    fake.text.side_effect = Exception("boom")
    with patch("core.search._ddgs_client", return_value=fake):
        assert web_search("anything") == []


def test_web_search_normalizes_none_result():
    fake = MagicMock()
    fake.text.return_value = None
    with patch("core.search._ddgs_client", return_value=fake):
        assert web_search("x") == []
