#!/usr/bin/env python
"""
auto_budget_guardian.py
=======================
Autonomous budget guardian for SupremeAI 2.0 free-tier providers.

Monitors free-tier usage across all AI providers and automatically pauses
any provider that exceeds 80% of its allocated quota (RPM, TPM, or RPD)
to prevent hard rate limits and service disruption.

Features:
- Periodic checks (every 5 minutes by default)
- Automatic pausing of providers at 80% threshold
- Automatic resumption after cooldown period (1 hour)
- Discord webhook notifications for alerts and recoveries
- Integration with existing FreeTierTracker singleton

Usage:
    python -m scripts.orchestrator.auto_budget_guardian
    # Or run as a background service
"""

import os
import time
import logging
from typing import Dict, Any
from datetime import datetime, timedelta

# Add the backend directory to the path so we can import from core
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../backend'))

from core.free_tier_tracker import get_tracker
from loguru import logger

# Configuration
CHECK_INTERVAL_SECONDS = int(os.getenv("BUDGET_GUARDIAN_INTERVAL", "300"))  # 5 minutes
THRESHOLD_PERCENT = float(os.getenv("BUDGET_GUARDIAN_THRESHOLD", "0.8"))   # 80%
PAUSE_DURATION_SECONDS = int(os.getenv("BUDGET_GUARDIAN_PAUSE_DURATION", "3600"))  # 1 hour
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Setup logging
logger.configure(
    handlers=[{"sink": sys.stderr, "level": "INFO"}]
)

def send_discord_notification(message: str) -> None:
    """Send a notification to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        logger.debug("Discord webhook not configured, skipping notification")
        return
    
    try:
        import requests
        payload = {
            "content": f"🤖 **SupremeAI Budget Guardian Alert**\n{message}"
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("Discord notification sent successfully")
    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")

def check_and_protect_budgets() -> None:
    """Check all providers and pause those exceeding threshold."""
    tracker = get_tracker()
    status = tracker.get_status()
    
    providers_to_pause: list[str] = []
    providers_to_resume: list[str] = []
    
    for provider_name, provider_status in status["providers"].items():
        # Skip if already paused (we don't want to double-pause)
        if provider_status.get("paused_until"):
            continue
            
        # Check each metric against threshold
        rpm_usage = provider_status["rpm_used"] / provider_status["rpm_limit"] if provider_status["rpm_limit"] > 0 else 0
        tpm_usage = provider_status["tpm_used"] / provider_status["tpm_limit"] if provider_status["tpm_limit"] > 0 else 0
        rpd_usage = provider_status["rpd_used"] / provider_status["rpd_limit"] if provider_status["rpd_limit"] > 0 else 0
        
        max_usage = max(rpm_usage, tpm_usage, rpd_usage)
        
        if max_usage >= THRESHOLD_PERCENT:
            providers_to_pause.append(provider_name)
            logger.warning(
                f"Provider {provider_name} exceeded {THRESHOLD_PERCENT*100}% usage: "
                f"RPM={rpm_usage:.2%}, TPM={tpm_usage:.2%}, RPD={rpd_usage:.2%}"
            )
    
    # Pause providers that are over threshold
    for provider in providers_to_pause:
        tracker._budgets[provider].pause(PAUSE_DURATION_SECONDS)
        msg = (
            f"🚨 **{provider.upper()} PAUSED** due to high usage\n"
            f"• RPM: {provider_status['rpm_used']}/{provider_status['rpm_limit']} "
            f"({provider_status['rpm_used']/provider_status['rpm_limit']*100:.1f}%)\n"
            f"• TPM: {provider_status['tpm_used']:,}/{provider_status['tpm_limit']:,} "
            f"({provider_status['tpm_used']/provider_status['tpm_limit']*100:.1f}%)\n"
            f"• RPD: {provider_status['rpd_used']}/{provider_status['rpd_limit']} "
            f"({provider_status['rpd_used']/provider_status['rpd_limit']*100:.1f}%)\n"
            f"• Paused for {PAUSE_DURATION_SECONDS//3600} hour(s)"
        )
        send_discord_notification(msg)
        logger.info(f"Paused {provider} for {PAUSE_DURATION_SECONDS} seconds")
    
    # Check for paused providers that might be ready to resume
    # (The tracker automatically resumes after pause duration, but we can log when they become available)
    for provider_name, provider_status in status["providers"].items():
        if provider_status.get("paused_until"):
            resume_time = datetime.fromtimestamp(provider_status["paused_until"])
            if datetime.now() >= resume_time:
                # It should have been auto-resumed by the tracker, but let's verify
                if tracker.is_available(provider_name):
                    providers_to_resume.append(provider_name)
    
    # Notify about resumed providers
    for provider in providers_to_resume:
        # We need to get the current status for this provider to report usage
        provider_status = status["providers"].get(provider, {})
        msg = (
            f"✅ **{provider.upper()} RESUMED** - Usage back below threshold\n"
            f"• RPM: {provider_status.get('rpm_used', 0)}/{provider_status.get('rpm_limit', 0)} "
            f"({provider_status.get('rpm_used', 0)/max(provider_status.get('rpm_limit', 1), 1)*100:.1f}%)\n"
            f"• TPM: {provider_status.get('tpm_used', 0):,}/{provider_status.get('tpm_limit', 0):,} "
            f"({provider_status.get('tpm_used', 0)/max(provider_status.get('tpm_limit', 1), 1)*100:.1f}%)\n"
            f"• RPD: {provider_status.get('rpd_used', 0)}/{provider_status.get('rpd_limit', 0)} "
            f"({provider_status.get('rpd_used', 0)/max(provider_status.get('rpd_limit', 1), 1)*100:.1f}%)"
        )
        send_discord_notification(msg)
        logger.info(f"Provider {provider} has resumed service")

def run_budget_guardian_check() -> None:
    """Execute a single budget guard check - designed to be called by external schedulers."""
    try:
        check_and_protect_budgets()
    except Exception as e:
        logger.error(f"Error in budget guardian check: {e}")
        if DISCORD_WEBHOOK_URL:
            try:
                import requests
                payload = {
                    "content": f"🆘 **Budget Guardian Check Failed**\n```{str(e)}```"
                }
                requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            except:
                pass  # Avoid recursive error handling

def main() -> None:
    """Main monitoring loop."""
    logger.info("Starting SupremeAI Budget Guardian...")
    logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS}s")
    logger.info(f"Pause threshold: {THRESHOLD_PERCENT*100}%")
    logger.info(f"Pause duration: {PAUSE_DURATION_SECONDS}s ({PAUSE_DURATION_SECONDS//3600}h)")
    
    if DISCORD_WEBHOOK_URL:
        logger.info("Discord notifications: ENABLED")
        send_discord_notification("🚨 **Budget Guardian Started**\nMonitoring free-tier usage across all providers.")
    else:
        logger.warning("Discord webhook not configured - notifications disabled")
    
    try:
        while True:
            check_and_protect_budgets()
            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Budget Guardian stopped by user")
        if DISCORD_WEBHOOK_URL:
            send_discord_notification("🛑 **Budget Guardian Stopped**")
    except Exception as e:
        logger.exception(f"Unexpected error in Budget Guardian: {e}")
        if DISCORD_WEBHOOK_URL:
            send_discord_notification(f"💥 **Budget Guardian Crashed**\n```{str(e)}```")
        raise

if __name__ == "__main__":
    main()