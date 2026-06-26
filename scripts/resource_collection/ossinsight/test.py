#!/usr/bin/env python3
"""
Test script for Ossinsight API client
"""

import sys
from pathlib import Path

# Add the resource_collection directory to sys.path
current_dir = Path(__file__).parent
resource_collection_dir = current_dir.parent
sys.path.insert(0, str(resource_collection_dir))

# Also add the parent of resource_collection to access base_api_client
root_dir = resource_collection_dir.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from ossinsight.client import main_ossinsight

if __name__ == "__main__":
    sys.exit(main_ossinsight())