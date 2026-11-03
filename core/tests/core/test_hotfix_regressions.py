import os
from unittest.mock import MagicMock, patch

import pytest


# 1. Test SUPABASE_SERVICE_ROLE_KEY check in production
def test_supabase_service_role_key_prod_check():
    from core.config import Settings

    # Temporarily remove SUPABASE_SERVICE_ROLE_KEY
    original_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if "SUPABASE_SERVICE_ROLE_KEY" in os.environ:
        del os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    os.environ["ENV"] = "production"

    with pytest.raises(
        ValueError, match="SUPABASE_SERVICE_ROLE_KEY is required in production environment."
    ):
        try:
            # Re-init settings and access property to trigger validation
            s = Settings(_env_file=None)
            _ = s.supabase_service_key
        except Exception as e:
            if original_key:
                os.environ["SUPABASE_SERVICE_ROLE_KEY"] = original_key
            del os.environ["ENV"]
            raise e

    if original_key:
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = original_key
    if "ENV" in os.environ:
        del os.environ["ENV"]


# 2. Test Rate Limiter Memory Limit
def test_rate_limiter_memory_limit():
    from core.rate_limit import _BOUNDED_CACHE_MAX

    assert _BOUNDED_CACHE_MAX <= 2000, "Fallback cache max size should be <= 2000"


# 3. Test Config RATE_LIMIT_USE_SIMPLIFIED prod default
def test_config_rate_limit_use_simplified_prod_default():
    from core.config import Settings

    os.environ["ENV"] = "production"
    # Ensure it's not set
    if "RATE_LIMIT_USE_SIMPLIFIED" in os.environ:
        del os.environ["RATE_LIMIT_USE_SIMPLIFIED"]

    # Should default to False in production
    s = Settings(_env_file=None)
    assert s.RATE_LIMIT_USE_SIMPLIFIED is False

    if "ENV" in os.environ:
        del os.environ["ENV"]
