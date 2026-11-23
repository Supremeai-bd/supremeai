# tests/test_create_cross_repo_patch.py
# বাংলা মন্তব্য: create_cross_repo_patch.py-এর CLI ও স্লাগ ফিল্টারিং লজিকের ইউনিট টেস্ট

from pathlib import Path
from scripts.ci.create_cross_repo_patch import sanitize_slug


def test_sanitize_slug():
    assert sanitize_slug("My Feature Slug!") == "my-feature-slug"
    assert sanitize_slug("sync/api_types--v2") == "sync-api_types-v2"
    assert sanitize_slug("---") == "patch"
    assert sanitize_slug("update-endpoints") == "update-endpoints"
