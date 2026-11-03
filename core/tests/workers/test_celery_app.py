import pytest

try:
    from workers.celery_app import app

    HAS_CELERY = app is not None
except Exception:
    HAS_CELERY = False


def test_celery_app_exposed():
    from workers.celery_app import app

    assert app is not None
