# ============================================================
# SupremeAI - Security Headers Configuration
# Production-Ready HTTP Security Headers Setup
# ============================================================

# ----------------------------------------------------------
# NGINX SECURITY HEADERS CONFIGURATION
# Add to nginx.conf or site-specific config block
# ----------------------------------------------------------

# /etc/nginx/conf.d/security-headers.conf

# ============================================================
# CORE SECURITY HEADERS
# ============================================================

# 1. Strict-Transport-Security (HSTS)
# Forces HTTPS connections for 1 year (including subdomains)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# 2. X-Content-Type-Options
# Prevents MIME-type sniffing
add_header X-Content-Type-Options "nosniff" always;

# 3. X-Frame-Options
# Prevents clickjacking attacks (deny all framing)
add_header X-Frame-Options "DENY" always;

# Alternative: Allow same-origin or specific origins
# add_header X-Frame-Options "SAMEORIGIN" always;
# add_header Content-Security-Policy "frame-ancestors 'self' https://app.supremeai.com;" always;

# 4. X-XSS-Protection
# Enables browser XSS filter (legacy, but still useful for older browsers)
add_header X-XSS-Protection "1; mode=block" always;

# 5. Referrer-Policy
# Controls how much referrer information is sent
add_header Referrer-Policy "strict-origin-when-cross-origin" always;

# 6. Content-Security-Policy (CSP)
# Comprehensive CSP to prevent XSS and injection attacks
add_header Content-Security-Policy "
    default-src 'self';
    script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net;
    style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net;
    img-src 'self' data: blob: https://*.supremeai.com https://*.gravatar.com;
    font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com;
    connect-src 'self' wss://*.supremeai.com https://api.supremeai.com https://staging-api.supremeai.com;
    media-src 'self' https://*.supremeai.com;
    object-src 'none';
    frame-ancestors 'none';
    base-uri 'self';
    form-action 'self';
    frame-src 'none';
    manifest-src 'self';
    worker-src 'self' blob:;
    upgrade-insecure-requests;
" always;

# 7. Permissions-Policy (formerly Feature-Policy)
# Controls which browser features can be used
add_header Permissions-Policy "
    accelerometer=(),
    ambient-light-sensor=(),
    autoplay=(self),
    battery=(),
    camera=(),
    clipboard-read=(self),
    clipboard-write=(self),
    display-capture=(),
    document-domain=(),
    encrypted-media=(),
    fullscreen=(self),
    geolocation=(),
    gyroscope=(),
    layout-animations=(self),
    legacy-image-formats=(self),
    magnetometer=(),
    microphone=(),
    midi=(),
    navigation-override=(),
    payment=(),
    picture-in-picture=(self),
    publickey-credentials-get=(self),
    screen-wake-lock=(self),
    speaker-selection=(self),
    sync-xhr=(self),
    unoptimized-images=(self),
    usb=(),
    web-share=(self),
    xr-spatial-tracking=()
" always;

# 8. Cross-Origin-Resource-Policy (CORP)
# Prevents cross-origin resource loading
add_header Cross-Origin-Resource-Policy "same-origin" always;

# 9. Cross-Origin-Embedder-Policy (COEP)
# Requires explicit CORS opt-in for cross-origin loading
add_header Cross-Origin-Embedder-Policy "require-corp" always;

# 10. Cross-Origin-Opener-Policy (COOP)
# Isolates browsing context for security
add_header Cross-Origin-Opener-Policy "same-origin" always;

# 11. Cache-Control (for sensitive endpoints)
# For API responses that should not be cached
# add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
# add_header Pragma "no-cache";
# add_header Expires "0";

# 12. Clear-Site-Data
# Clear sensitive data on logout (triggered via JavaScript)
# This header is set dynamically on logout endpoint
# add_header Clear-Site-Data "'cache', 'cookies', 'storage', 'executionContexts'"


# ============================================================
# FASTAPI/MIDDLEWARE IMPLEMENTATION
# Python implementation of security headers
# ============================================================

"""
app/middleware/security_headers.py
Security Headers Middleware for FastAPI Application
"""

from fast import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import os


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add comprehensive security headers to all responses.
    
    Implements OWASP recommended security headers:
    - HSTS (HTTP Strict Transport Security)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    - And more...
    """
    
    # CSP Configuration (can be overridden per environment)
    CSP_DIRECTIVES = {
        "default-src": ["'self'"],
        "script-src": [
            "'self'", 
            "'unsafe-inline'",
            # Add CDN domains here if needed
        ],
        "style-src": [
            "'self'", 
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
        ],
        "img-src": [
            "'self'", 
            "data:", 
            "blob:",
        ],
        "font-src": [
            "'self'", 
            "https://fonts.gstatic.com",
        ],
        "connect-src": [
            "'self'",
            # WebSocket and API URLs
        ],
        "object-src": ["'none'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-src": ["'none'"],
        "upgrade-insecure-requests": None,
    }
    
    async def dispatch(
        self, 
        request: Request, 
        call_next: Callable
    ) -> Response:
        """
        Process request and add security headers to response.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/endpoint handler
            
        Returns:
            Response with security headers added
        """
        response = await call_next(request)
        
        # Apply security headers
        self._add_security_headers(response, request)
        
        return response
    
    def _add_security_headers(
        self, 
        response: Response, 
        request: Request
    ) -> None:
        """Add all security headers to the response."""
        
        # 1. Strict Transport Security (HSTS)
        # Only set in production with HTTPS
        if self._is_https(request):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; "
                "includeSubDomains; "
                "preload"
            )
        
        # 2. X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 3. X-Frame-Options
        response.headers["X-Frame-Options"] = "DENY"
        
        # 4. X-XSS-Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # 5. Referrer Policy
        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )
        
        # 6. Content Security Policy
        csp = self._build_csp()
        response.headers["Content-Security-Policy"] = csp
        
        # 7. Permissions Policy
        permissions_policy = self._build_permissions_policy()
        response.headers["Permissions-Policy"] = permissions_policy
        
        # 8. Cross-Origin Headers
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        
        # 9. Remove server information
        response.headers.pop("Server", None)
        response.headers["X-Powered-By"] = None
        
        # 10. Additional security headers
        response.headers["X-DNS-Prefetch-Control"] = "off"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        
        # 11. API-specific headers
        if request.url.path.startswith("/api/"):
            self._add_api_headers(response)
    
    def _is_https(self, request: Request) -> bool:
        """Check if request is over HTTPS."""
        return (
            request.url.scheme == "https" or
            request.headers.get("x-forwarded-proto") == "https"
        )
    
    def _build_csp(self) -> str:
        """Build Content-Security-Policy string from directives."""
        parts = []
        
        for directive, values in self.CSP_DIRECTIVES.items():
            if values is None:
                parts.append(directive)
            else:
                parts.append(f"{directive} {' '.join(values)}")
        
        return "; ".join(parts)
    
    def _build_permissions_policy(self) -> str:
        """Build Permissions-Policy string."""
        policies = {
            "accelerometer": "()",
            "ambient-light-sensor": "()",
            "camera": "()",
            "geolocation": "()",
            "gyroscope": "()",
            "magnetometer": "()",
            "microphone": "()",
            "midi": "()",
            "payment": "()",
            "usb": "()",
            "fullscreen": "(self)",
            "screen-wake-lock": "(self)",
        }
        
        return ", ".join(
            f"{k}={v}" for k, v in policies.items()
        )
    
    def _add_api_headers(self, response: Response) -> None:
        """Add headers specific to API responses."""
        
        # Prevent caching of API responses by default
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, proxy-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"


# FastAPI app integration example
"""
from fastapi import FastAPI
from app.middleware.security_headers import SecurityHeadersMiddleware

app = FastAPI()

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Or conditionally based on environment
import os
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(SecurityHeadersMiddleware)
"""


# ============================================================
# CORS CONFIGURATION
# Secure CORS settings for API access
# ============================================================

"""
app/config/cors.py
CORS Configuration for SupremeAI
"""

from fastapi.middleware.cors import CORSMiddleware
import os


def get_cors_config() -> dict:
    """
    Get CORS configuration based on environment.
    
    Returns:
        Dictionary with CORS settings
    """
    # Allowed origins (strict in production)
    allowed_origins = [
        "https://app.supremeai.com",      # Production frontend
        "https://dashboard.supremeai.com", # Admin dashboard
    ]
    
    # Development origins
    if os.getenv("ENVIRONMENT") in ("development", "staging"):
        allowed_origins.extend([
            "http://localhost:3000",       # React dev server
            "http://localhost:5173",       # Vite dev server
            "http://localhost:8000",       # FastAPI dev server
            "http://127.0.0.1:3000",
        ])
    
    # Also check environment variable for additional origins
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        allowed_origins.extend(
            origin.strip() for origin in env_origins.split(",") if origin.strip()
        )
    
    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,  # Required for cookies/auth tokens
        "allow_methods": [
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        "allow_headers": [
            "Accept",
            "Accept-Language",
            "Authorization",
            "Content-Type",
            "Content-Language",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-API-Version",
            "X-Request-ID",
        ],
        "expose_headers": [
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-API-Version",
            "Deprecation",
            "Sunset",
            "Link",
        ],
        "max_age": 600,  # Pre-flight cache for 10 minutes
    }


def setup_cors(app) -> None:
    """Configure CORS middleware for FastAPI application."""
    cors_config = get_cors_config()
    
    app.add_middleware(
        CORSMiddleware,
        **cors_config
    )


# ============================================================
# RATE LIMITING HEADERS
# Rate limit information in response headers
# ============================================================

class RateLimitHeaders:
    """Add rate limiting information to responses."""
    
    @staticmethod
    def add_rate_limit_headers(
        response: Response,
        limit: int,
        remaining: int,
        reset_time: int
    ) -> None:
        """
        Add standard rate limit headers.
        
        Args:
            response: HTTP response object
            limit: Maximum requests allowed
            remaining: Requests remaining in window
            reset_time: Unix timestamp when window resets
        """
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        if remaining <= 0:
            response.status_code = 429
            response.headers["Retry-After"] = str(
                max(0, reset_time - int(time.time()))
            )


# ============================================================
# API VERSIONING HEADERS
# Version compatibility headers
# ============================================================

class APIVersionHeaders:
    """Add API versioning and deprecation headers."""
    
    CURRENT_VERSION = "v1"
    SUPPORTED_VERSIONS = ["v1"]
    SUNSET_DATE = "2026-06-01"  # When v1 will be retired
    
    @staticmethod
    def add_version_headers(response: Response, version: str) -> None:
        """Add version-related headers."""
        response.headers["X-API-Version"] = version
        
        if version not in APIVersionHeaders.SUPPORTED_VERSIONS:
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = APIVersionHeaders.SUNSET_DATE
            response.headers["Link"] = (
                f"</api/{APIVersionHeaders.CURRENT_VERSION}/>; "
                f'rel="successor-version"'
            )


# ============================================================
# SECURITY HEADER VALIDATION TESTS
# Verify headers are correctly configured
# ============================================================

"""
tests/unit/test_security_headers.py
Unit tests for security headers configuration
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient


@pytest.mark.unit
async def test_hsts_header_present(client: AsyncClient):
    """Test HSTS header is set correctly."""
    response = await client.get("/api/v1/admin/health")
    
    assert "Strict-Transport-Security" in response.headers
    hsts_value = response.headers["Strict-Transport-Security"]
    assert "max-age=" in hsts_value
    assert "includeSubDomains" in hsts_value


@pytest.mark.unit
async def test_x_content_type_options(client: AsyncClient):
    """Test X-Content-Type-Options header."""
    response = await client.get("/api/v1/admin/health")
    
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


@pytest.mark.unit
async def test_x_frame_options(client: AsyncClient):
    """Test X-Frame-Options prevents clickjacking."""
    response = await client.get("/api/v1/admin/health")
    
    assert response.headers.get("X-Frame-Options") == "DENY"


@pytest.mark.unit
async def test_csp_header_present(client: AsyncClient):
    """Test Content-Security-Policy is configured."""
    response = await client.get("/api/v1/admin/health")
    
    csp = response.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "default-src" in csp
    assert "object-src 'none'" in csp


@pytest.mark.unit
async def test_server_info_not_leaked(client: AsyncClient):
    """Test Server header doesn't reveal technology info."""
    response = await client.get("/api/v1/admin/health")
    
    # Server header should be absent or generic
    server = response.headers.get("Server", "")
    assert "nginx" not in server.lower() or server == ""
    assert "python" not in server.lower()


@pytest.mark.unit
async def test_api_no_cache_headers(client: AsyncClient):
    """Test API responses have proper cache control."""
    response = await client.get("/api/v1/admin/health")
    
    cache_control = response.headers.get("Cache-Control", "")
    assert "no-store" in cache_control or "private" in cache_control


@pytest.mark.unit
async def test_cors_headers_on_options(client: AsyncClient):
    """Test CORS preflight headers are correct."""
    response = await client.options(
        "/api/v1/agents",
        headers={
            "Origin": "https://app.supremeai.com",
            "Access-Control-Request-Method": "GET",
        }
    )
    
    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" in response.headers
    assert "Access-Control-Allow-Methods" in response.headers


# ============================================================
# DEPLOYMENT CHECKLIST
# Verify security headers in production
# ============================================================

SECURITY_HEADERS_CHECKLIST = """
## Production Deployment - Security Headers Verification

### Pre-Deployment Checks

Run this checklist before deploying to production:

#### 1. Header Presence Check
```bash
curl -I https://api.supremeai.com/api/v1/admin/health | grep -E \
    "(Strict-Transport|X-Content-Type|X-Frame|X-XSS|Content-Security|Referrer)"
```

**Expected Output:**
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; ...
Referrer-Policy: strict-origin-when-cross-origin
```

#### 2. SSL/TLS Configuration Check
```bash
openssl s_client -connect api.supremeai.com:443 \
    -servername api.supremeai.com </dev/null 2>/dev/null | \
    grep -E "(Protocol|Cipher)"
```

**Expected:** TLSv1.2 or TLSv1.3 only, strong cipher suites

#### 3. Security Headers Scoring
Use online tools to verify:
- [Security Headers](https://securityheaders.com/)
- [Mozilla Observatory](https://observatory.mozilla.org/)
- [SSL Labs](https://www.ssllabs.com/ssltest/)

**Target Scores:**
- Security Headers: A+ grade
- Mozilla Observatory: A+ grade
- SSL Labs: A grade (90+)

### Continuous Monitoring

Set up automated monitoring:

```bash
# Cron job to check headers daily
#!/bin/bash
curl -s https://api.supremeai.com/api/v1/admin/health > /tmp/headers.txt

if ! grep -q "Strict-Transport-Security" /tmp/headers.txt; then
    echo "ALERT: Missing HSTS header!" | mail -s "Security Alert" security@supremeai.com
fi
```

### Incident Response

If security headers are missing or misconfigured:

1. **Immediate**: Block deployment, investigate cause
2. **Short-term**: Revert to last known good configuration
3. **Root Cause**: Audit recent changes, check CI/CD pipeline
4. **Prevention**: Add automated header checks to deployment pipeline
"""

print(SECURITY_HEADERS_CHECKLIST)
