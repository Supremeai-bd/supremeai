#!/usr/bin/env python3
"""
Test script for the ToolRanker
"""

import sys
import os

# Add the current directory to the path so we can import core_engine
sys.path.insert(0, os.path.dirname(__file__))

from core_engine.tool_ranker import demo_ranker

if __name__ == "__main__":
    demo_ranker()