from unittest.mock import MagicMock, patch

from core.search import web_search


def test_web_search_returns_empty_when_client_unavailable():
    with patch("core.search._ddgs_client", return_value=None):
        assert web_search("python") == []


def test_web_search_returns_results_from_client():
    fake = MagicMock()
    fake.text.return_value = [{"title": "a", "href": "b", "body": "c"}]
    with patch("core.search._ddgs_client", return_value=fake), patch("core.search.time.sleep"):
        result = web_search("python", max_results=3)
    assert result == [{"title": "a", "href": "b", "body": "c"}]
    fake.text.assert_called_with("python", max_results=3)


def test_web_search_retries_transient_ddg_failures():
    # বাংলা মন্তব্য: লাইভ নেটওয়ার্কে DDG ক্ষণস্থায়ী timeout দেয় — ২য় চেষ্টায় সফল হওয়া উচিত।
    fake = MagicMock()
    fake.text.side_effect = [Exception("timeout"), [{"title": "ok", "href": "u", "body": "b"}]]
    with patch("core.search._ddgs_client", return_value=fake), patch("core.search.time.sleep"):
        result = web_search("python", max_results=3)
    assert result == [{"title": "ok", "href": "u", "body": "b"}]
    assert fake.text.call_count == 2


def test_web_search_returns_empty_on_client_error():
    fake = MagicMock()
    fake.text.side_effect = Exception("boom")
    with patch("core.search._ddgs_client", return_value=fake), patch("core.search.time.sleep"):
        assert web_search("anything") == []


def test_web_search_normalizes_none_result():
    # বাংলা মন্তব্য: সব রিট্রাই-এ None হলেও ফাঁকা লিস্টই চুক্তি।
    fake = MagicMock()
    fake.text.return_value = None
    with patch("core.search._ddgs_client", return_value=fake), patch("core.search.time.sleep"):
        assert web_search("x") == []


def test_empty_result_has_no_retries_or_delay():
    fake = MagicMock()
    fake.text.return_value = []
    with patch("core.search._ddgs_client", return_value=fake), patch("core.search.time.sleep") as sleep:
        assert web_search("no matches") == []
    assert fake.text.call_count == 1
    sleep.assert_not_called()


def test_error_retries_sleep_only_between_attempts():
    fake = MagicMock()
    fake.text.side_effect = RuntimeError("failure")
    with patch("core.search._ddgs_client", return_value=fake), patch("core.search.time.sleep") as sleep:
        assert web_search("offline") == []
    assert fake.text.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [0.5, 1.0]
