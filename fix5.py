with open('backend/tests/core/test_security.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('patch("core.rate_limiter.redis_manager.get_client_async"', 'patch("middleware.rate_limiter.redis_manager.get_client_async"')
c = c.replace('from core.rate_limiter import AsyncRateLimiter', 'from middleware.rate_limiter import AsyncRateLimiter')

with open('backend/tests/core/test_security.py', 'w', encoding='utf-8') as f:
    f.write(c)
