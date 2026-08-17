#!/usr/bin/env python3
"""
Internet Monitor Agent Demo
==========================
Demonstration script showing how the internet monitoring agent works.
"""

import asyncio
import json
from datetime import datetime

from agents.internet_monitor_agent import internet_monitor_agent


async def main():
    """Main demo function."""
    print("🚀 Starting Internet Monitor Agent Demo")
    print("=" * 50)
    
    # Initialize the agent
    print("🔧 Initializing Internet Monitor Agent...")
    await internet_monitor_agent.initialize()
    print("✅ Agent initialized successfully!")
    print()
    
    # Show system capabilities
    print("📋 Current System Capabilities:")
    capabilities = await internet_monitor_agent.get_system_capabilities()
    print(f"   Features discovered: {len(capabilities.get('features', []))}")
    for i, feature in enumerate(capabilities.get('features', [])[:10], 1):  # Show first 10
        print(f"   {i}. {feature}")
    if len(capabilities.get('features', [])) > 10:
        print(f"   ... and {len(capabilities.get('features', [])) - 10} more")
    print()
    
    # Get latest updates
    print("🌐 Fetching latest internet updates...")
    updates = await internet_monitor_agent.get_latest_updates()
    print(f"✅ Found {len(updates)} updates")
    print()
    
    # Show update summary
    print("📊 Update Summary:")
    summary = await internet_monitor_agent.get_update_summary()
    print(f"   Total updates: {summary['total_updates']}")
    print("   By category:")
    for category, items in summary['by_category'].items():
        if items:
            print(f"     • {category}: {len(items)} updates")
    print()
    
    # Show top updates
    print("🔥 Top Updates:")
    for i, update in enumerate(summary['top_updates'][:5], 1):
        print(f"   {i}. [{update.category}] {update.title}")
        print(f"      Source: {update.source}")
        print(f"      Time: {update.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if update.url:
            print(f"      URL: {update.url}")
        print()
    
    # Show detailed updates by category
    print("🔍 Detailed Updates by Category:")
    for category, items in summary['by_category'].items():
        if items:
            print(f"\n   📁 {category.upper()}:")
            for item in items[:3]:  # Show first 3 of each category
                print(f"     • {item['title']}")
                print(f"       {item['description'][:100]}{'...' if len(item['description']) > 100 else ''}")
    
    print("\n🎯 Demo completed successfully!")
    print("\n💡 The Internet Monitor Agent runs continuously in the background,")
    print("   checking for updates at regular intervals and notifying admins")
    print("   about new GitHub trends, AI developments, and system gaps.")


if __name__ == "__main__":
    asyncio.run(main())