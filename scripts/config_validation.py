# scripts/config_validation.py
"""Configuration Validation Script for SupremeAI 2.0

This script validates all configuration components of the SupremeAI 2.0 project.
"""

import asyncio
import sys
import os

# Add backend to the path to allow imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.core.config import settings
from backend.core.health_check import health_checker
from backend.services.internet_monitor_service import internet_monitor_service


async def validate_config():
    """Validate the application configuration."""
    print("🔍 Starting configuration validation...")
    
    validation_results = []
    
    # Validate basic settings
    print("\n📋 Validating basic settings...")
    try:
        assert settings.env in ["local", "staging", "production"], f"Invalid environment: {settings.env}"
        print("✅ Environment setting is valid")
        validation_results.append(("Environment", True, "Valid environment"))
    except Exception as e:
        print(f"❌ Environment validation failed: {e}")
        validation_results.append(("Environment", False, str(e)))
    
    # Validate API keys are set
    print("\n🔑 Validating API keys...")
    api_keys_valid = True
    if not settings.gemini_api_key:
        print("⚠️  Gemini API key not set (may be OK in some environments)")
        validation_results.append(("Gemini API Key", True, "Not set but may be OK"))
    else:
        print("✅ Gemini API key is set")
        validation_results.append(("Gemini API Key", True, "Set"))
    
    if not settings.openrouter_api_key:
        print("⚠️  OpenRouter API key not set (may be OK in some environments)")
        validation_results.append(("OpenRouter API Key", True, "Not set but may be OK"))
    else:
        print("✅ OpenRouter API key is set")
        validation_results.append(("OpenRouter API Key", True, "Set"))
    
    # Validate CORS settings
    print("\n🌐 Validating CORS settings...")
    try:
        assert isinstance(settings.cors_origins, list), "CORS origins should be a list"
        print(f"✅ CORS origins configured: {len(settings.cors_origins)} origins")
        validation_results.append(("CORS Origins", True, f"{len(settings.cors_origins)} origins"))
    except Exception as e:
        print(f"❌ CORS validation failed: {e}")
        validation_results.append(("CORS Origins", False, str(e)))
    
    # Validate database settings
    print("\n💾 Validating database settings...")
    try:
        if settings.supabase_database_url:
            print("✅ Database URL is configured")
            validation_results.append(("Database URL", True, "Configured"))
        else:
            print("⚠️  Database URL not set (may be OK in some environments)")
            validation_results.append(("Database URL", True, "Not set but may be OK"))
    except Exception as e:
        print(f"❌ Database validation failed: {e}")
        validation_results.append(("Database URL", False, str(e)))
    
    # Validate Redis settings
    print("\n.Redis Validating Redis settings...")
    try:
        if settings.redis_url:
            print("✅ Redis URL is configured")
            validation_results.append(("Redis URL", True, "Configured"))
        else:
            print("⚠️  Redis URL not set (may be OK in some environments)")
            validation_results.append(("Redis URL", True, "Not set but may be OK"))
    except Exception as e:
        print(f"❌ Redis validation failed: {e}")
        validation_results.append(("Redis URL", False, str(e)))
    
    # Run health checks
    print("\n🏥 Running system health checks...")
    try:
        health_status = await health_checker.check_all()
        overall_status = health_status["status"]
        print(f"🏥 Overall system health: {overall_status}")
        print(f"📊 Health checks summary: {health_status['summary']}")
        
        validation_results.append(("System Health", True, f"Overall: {overall_status}"))
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        validation_results.append(("System Health", False, str(e)))
    
    # Validate internet monitor service initialization
    print("\n📡 Validating internet monitor service...")
    try:
        # Try to initialize the service
        await internet_monitor_service.initialize()
        print("✅ Internet monitor service initialized")
        validation_results.append(("Internet Monitor", True, "Initialized"))
    except Exception as e:
        print(f"⚠️  Internet monitor service initialization failed: {e}")
        validation_results.append(("Internet Monitor", False, str(e)))
    
    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    total_checks = len(validation_results)
    passed_checks = sum(1 for _, passed, _ in validation_results if passed)
    
    for name, passed, message in validation_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {name:<25} - {message}")
    
    print(f"\n📊 Total: {total_checks}, Passed: {passed_checks}, Failed: {total_checks - passed_checks}")
    
    if passed_checks == total_checks:
        print("\n🎉 All configuration validations passed!")
        return True
    else:
        print(f"\n⚠️  {total_checks - passed_checks} validation(s) failed.")
        return False


if __name__ == "__main__":
    success = asyncio.run(validate_config())
    sys.exit(0 if success else 1)