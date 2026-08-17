# tests/test_middleware_anti_hacking.py
"""Tests for the anti-hacking middleware."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers

from backend.middleware.anti_hacking import (
    AntiHackingContextMiddleware,
    _octet3
)


def test_octet3_ipv4():
    """Test the _octet3 function with IPv4 addresses."""
    assert _octet3("192.168.1.100") == "192.168.1"
    assert _octet3("10.0.0.1") == "10.0.0"
    assert _octet3("8.8.8.8") == "8.8.8"


def test_octet3_non_ipv4():
    """Test the _octet3 function with non-IPv4 addresses."""
    assert _octet3("2001:db8::1") == "2001:db8::1"  # IPv6 remains unchanged
    assert _octet3("invalid_ip") == "invalid_ip"  # Invalid IP remains unchanged
    assert _octet3("192.168.1") == "192.168.1"  # Incomplete IPv4 remains unchanged
    assert _octet3("") == ""  # Empty string remains unchanged


def test_octet3_edge_cases():
    """Test the _octet3 function with edge cases."""
    assert _octet3("1.2.3.4.5") == "1.2.3"  # More than 4 octets
    assert _octet3("1.2") == "1.2"  # Less than 4 octets
    assert _octet3("192.168.1.256") == "192.168.1"  # Valid IPv4 with large number


@pytest.mark.asyncio
async def test_dispatch_non_admin_request():
    """Test middleware dispatch for non-admin requests."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request without admin user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"user-agent", b"test-agent"),
        ],
    })
    
    # Mock call_next to return a simple response
    call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
    
    response = await middleware.dispatch(request, call_next)
    
    # Verify that security_signal was added to request state
    assert hasattr(request.state, 'security_signal')
    assert request.state.security_signal["ip"] == "192.168.1.100"
    assert request.state.security_signal["ua"] == "test-agent"
    
    # Verify call_next was called
    call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_request_no_previous_context():
    """Test middleware dispatch for admin request with no previous context."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"test-agent"),
            (b"x-device-fingerprint", b"device123"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock Redis manager
    with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
        mock_redis_manager.client = AsyncMock()
        mock_redis_manager.get_cache = AsyncMock(return_value=None)  # No previous context
        mock_redis_manager.set_cache = AsyncMock()
        
        # Mock send_otp function
        with patch('backend.middleware.anti_hacking.send_otp') as mock_send_otp:
            # Mock call_next to return a simple response
            call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
            
            response = await middleware.dispatch(request, call_next)
            
            # Verify that security_signal was added to request state
            assert hasattr(request.state, 'security_signal')
            assert request.state.security_signal["ip"] == "192.168.1.100"
            
            # Verify that context was stored in Redis
            mock_redis_manager.set_cache.assert_called()
            
            # Verify call_next was called
            call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_request_matching_context():
    """Test middleware dispatch for admin request with matching context."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"test-agent"),
            (b"x-device-fingerprint", b"device123"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock Redis manager with matching context
    with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
        mock_redis_manager.client = AsyncMock()
        previous_context = {
            "ip": "192.168.1.100",
            "country": "US", 
            "ua": "test-agent",
            "fingerprint": "device123"
        }
        mock_redis_manager.get_cache = AsyncMock(return_value=json.dumps(previous_context))
        mock_redis_manager.set_cache = AsyncMock()
        
        # Mock call_next to return a simple response
        call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
        
        response = await middleware.dispatch(request, call_next)
        
        # Verify that security_signal was added to request state
        assert hasattr(request.state, 'security_signal')
        assert request.state.security_signal["ip"] == "192.168.1.100"
        
        # Verify that context was updated in Redis
        mock_redis_manager.set_cache.assert_called()
        
        # Verify call_next was called
        call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_request_context_mismatch_alert_only():
    """Test middleware dispatch for admin request with context mismatch in alert-only mode."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user — different IP AND different UA triggers OTP
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.2.100"),  # Different IP + different subnet
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"completely-different-agent"),  # Different UA → OTP fires
            (b"x-device-fingerprint", b"device-new"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock settings to be in alert-only mode (enforce_anti_hacking = False)
    with patch('backend.middleware.anti_hacking.settings') as mock_settings:
        mock_settings.enforce_anti_hacking = False
        mock_settings.otp_cooldown_seconds = 300
        
        # Mock Redis manager with different context
        with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
            mock_redis_manager.client = AsyncMock()
            previous_context = {
                "ip": "192.168.1.100",  # Previous IP (different subnet)
                "country": "US",
                "ua": "test-agent",      # Different from new request UA
                "fingerprint": "device123"
            }
            mock_redis_manager.get_cache = AsyncMock(return_value=json.dumps(previous_context))
            mock_redis_manager.set_cache = AsyncMock()
            
            # Mock send_otp function
            with patch('backend.middleware.anti_hacking.send_otp') as mock_send_otp:
                # Mock call_next to return a simple response
                call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
                
                response = await middleware.dispatch(request, call_next)
                
                # Verify that security_signal was added to request state
                assert hasattr(request.state, 'security_signal')
                
                # Verify that OTP was sent
                mock_send_otp.assert_called_once()
                
                # Verify that security_otp_pending is set
                assert request.state.security_otp_pending is True
                
                # Verify call_next was called (because in alert-only mode, it continues)
                call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_request_context_mismatch_enforce_mode():
    """Test middleware dispatch for admin request with context mismatch in enforce mode."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request — different subnet AND different UA → OTP fires + 403
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.2.100"),  # Different IP + different subnet
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"completely-different-agent"),  # Different UA
            (b"x-device-fingerprint", b"device-new"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock settings to be in enforce mode (enforce_anti_hacking = True)
    with patch('backend.middleware.anti_hacking.settings') as mock_settings:
        mock_settings.enforce_anti_hacking = True
        mock_settings.otp_cooldown_seconds = 300
        
        # Mock Redis manager with different context
        with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
            mock_redis_manager.client = AsyncMock()
            previous_context = {
                "ip": "192.168.1.100",  # Previous IP (different subnet)
                "country": "US",
                "ua": "test-agent",      # Different from new request UA
                "fingerprint": "device123"
            }
            mock_redis_manager.get_cache = AsyncMock(return_value=json.dumps(previous_context))
            mock_redis_manager.set_cache = AsyncMock()
            
            # Mock Redis SET command for cooldown
            mock_redis_manager.client.set = AsyncMock(return_value=True)  # Successfully acquire lock
            
            # Mock send_otp function
            with patch('backend.middleware.anti_hacking.send_otp') as mock_send_otp:
                # Mock call_next to return a simple response
                call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
                
                response = await middleware.dispatch(request, call_next)
                
                # Should return a 403 response instead of calling next
                assert response.status_code == 403
                assert json.loads(response.body) == {
                    "error": "context_mismatch",
                    "detail": "OTP verification required — check your configured channel.",
                }
                
                # Verify that OTP was sent
                mock_send_otp.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_request_same_subnet_ua_caution():
    """Test middleware dispatch for admin request with same subnet/UA (caution mode)."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.200"),  # Same subnet as previous
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"test-agent"),  # Same UA as previous
            (b"x-device-fingerprint", b"device123"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock Redis manager with similar context (different IP but same subnet/UA)
    with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
        mock_redis_manager.client = AsyncMock()
        previous_context = {
            "ip": "192.168.1.100",  # Previous IP (same subnet)
            "country": "US",
            "ua": "test-agent",  # Same UA
            "fingerprint": "device123"
        }
        mock_redis_manager.get_cache = AsyncMock(return_value=json.dumps(previous_context))
        mock_redis_manager.set_cache = AsyncMock()
        
        # Mock call_next to return a simple response
        call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
        
        response = await middleware.dispatch(request, call_next)
        
        # In caution mode, it should continue normally
        call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_request_otp_cooldown_active():
    """Test middleware dispatch when OTP cooldown is active."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request — different subnet AND different UA → triggers mismatch + cooldown
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.2.100"),  # Different IP + different subnet
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"completely-different-agent"),  # Different UA
            (b"x-device-fingerprint", b"device-new"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock settings
    with patch('backend.middleware.anti_hacking.settings') as mock_settings:
        mock_settings.enforce_anti_hacking = True
        mock_settings.otp_cooldown_seconds = 300
        
        # Mock Redis manager with different context
        with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
            mock_redis_manager.client = AsyncMock()
            previous_context = {
                "ip": "192.168.1.100",  # Previous IP (different subnet)
                "country": "US",
                "ua": "test-agent",      # Different from new request UA
                "fingerprint": "device123"
            }
            mock_redis_manager.get_cache = AsyncMock(return_value=json.dumps(previous_context))
            
            # Mock Redis SET command to return False (cooldown active)
            mock_redis_manager.client.set = AsyncMock(return_value=False)  # Cooldown active
            
            # Mock send_otp function
            with patch('backend.middleware.anti_hacking.send_otp') as mock_send_otp:
                # Mock call_next to return a simple response
                call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
                
                response = await middleware.dispatch(request, call_next)
                
                # Should return a 403 response with cooldown message
                assert response.status_code == 403
                assert "OTP verification required" in response.body.decode()
                
                # Verify that OTP was NOT sent (due to cooldown)
                mock_send_otp.assert_not_called()
                
                # Verify security_otp_pending is set
                assert request.state.security_otp_pending is True


@pytest.mark.asyncio
async def test_dispatch_with_redis_disabled():
    """Test middleware dispatch when Redis is not available."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"test-agent"),
            (b"x-device-fingerprint", b"device123"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock Redis manager as None/disabled
    with patch('backend.middleware.anti_hacking.redis_manager', None):
        # Mock call_next to return a simple response
        call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
        
        response = await middleware.dispatch(request, call_next)
        
        # Should continue normally despite Redis being unavailable
        call_next.assert_called_once()
        
        # Verify that security_signal was still added
        assert hasattr(request.state, 'security_signal')


@pytest.mark.asyncio
async def test_dispatch_with_redis_client_none():
    """Test middleware dispatch when Redis client is None."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"cf-ipcountry", b"US"),
            (b"user-agent", b"test-agent"),
            (b"x-device-fingerprint", b"device123"),
        ],
    })
    request.state.user = {"sub": "admin123"}
    
    # Mock Redis manager with None client
    with patch('backend.middleware.anti_hacking.redis_manager') as mock_redis_manager:
        mock_redis_manager.client = None
        mock_redis_manager.get_cache = AsyncMock(return_value=None)
        mock_redis_manager.set_cache = AsyncMock()
        
        # Mock call_next to return a simple response
        call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
        
        response = await middleware.dispatch(request, call_next)
        
        # Should continue normally despite Redis client being None
        call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_no_sub_attribute():
    """Test middleware dispatch for admin user without sub attribute."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with admin user that has no 'sub' attribute
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"user-agent", b"test-agent"),
        ],
    })
    request.state.user = {"id": "admin123"}  # No 'sub' attribute
    
    # Mock call_next to return a simple response
    call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
    
    response = await middleware.dispatch(request, call_next)
    
    # Should handle gracefully and continue
    call_next.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_admin_user_none():
    """Test middleware dispatch for request with no user."""
    middleware = AntiHackingContextMiddleware(AsyncMock())  # Mock app
    
    # Create a mock request with no user
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"x-forwarded-for", b"192.168.1.100"),
            (b"user-agent", b"test-agent"),
        ],
    })
    # No user attribute
    
    # Mock call_next to return a simple response
    call_next = AsyncMock(return_value=JSONResponse(content={"test": "response"}))
    
    response = await middleware.dispatch(request, call_next)
    
    # Should handle gracefully and continue
    call_next.assert_called_once()