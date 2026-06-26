"""
Ossinsight API client for SupremeAI resource collection
"""

import sys
from pathlib import Path

# Add the parent directory to sys.path to import base classes
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from base_api_client import BaseAPIClient
import requests
from typing import Dict, List, Any, Optional
import json
import logging
from datetime import datetime
import time


class OssinsightClient(BaseAPIClient):
    """Client for OSS Insight API"""
    
    def __init__(self, data_dir: Path):
        super().__init__(
            name="ossinsight",
            base_url="https://api.ossinsight.io/v1",
            data_dir=data_dir
            # No API key required for basic usage (beta)
        )
    
    def fetch_data(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Fetch data from OSS Insight API"""
        return self._make_request(endpoint, params)
    
    def parse_data(self, raw_data: Any, endpoint: str) -> List[Dict[str, Any]]:
        """Parse OSS Insight API response into standardized format"""
        if not isinstance(raw_data, dict):
            self.logger.warning(f"Expected dict response from {endpoint}, got {type(raw_data)}")
            return []
        
        # Handle OSS Insight's specific response format
        # Based on observation: {"type":"sql_endpoint","data":{"columns":[{...}],"rows":[{...}]},"result":{...}}
        if 'type' in raw_data and raw_data.get('type') == 'sql_endpoint' and 'data' in raw_data:
            data_section = raw_data['data']
            
            # Handle the format where rows are already objects with correct property names
            if 'rows' in data_section and isinstance(data_section['rows'], list):
                rows = data_section['rows']
                
                # Convert rows to dictionaries (they already are, but ensure they have metadata)
                result = []
                for row in rows:
                    if isinstance(row, dict):
                        # Add metadata
                        row['_api_source'] = 'ossinsight'
                        row['_endpoint'] = endpoint
                        result.append(row)
                    else:
                        self.logger.warning(f"Skipping non-dict row in {endpoint}: {type(row)}")
                
                return result
            else:
                # Fallback: if no rows but we have data, try to use data directly
                if isinstance(data_section, list):
                    result = []
                    for item in data_section:
                        if isinstance(item, dict):
                            item['_api_source'] = 'ossinsight'
                            item['_endpoint'] = endpoint
                            result.append(item)
                    return result
                elif isinstance(data_section, dict):
                    data_section['_api_source'] = 'ossinsight'
                    data_section['_endpoint'] = endpoint
                    return [data_section]
        else:
            # Handle standard JSON responses
            data = []
            
            # Check if it's a list response
            if isinstance(raw_data, list):
                data = raw_data
            # Check if it's an object with a 'data' or 'items' or 'list' field
            elif isinstance(raw_data, dict):
                # Common patterns for API responses
                if 'data' in raw_data and isinstance(raw_data['data'], list):
                    data = raw_data['data']
                elif 'items' in raw_data and isinstance(raw_data['items'], list):
                    data = raw_data['items']
                elif 'list' in raw_data and isinstance(raw_data['list'], list):
                    data = raw_data['list']
                elif 'repositories' in raw_data and isinstance(raw_data['repositories'], list):
                    data = raw_data['repositories']
                elif 'collections' in raw_data and isinstance(raw_data['collections'], list):
                    data = raw_data['collections']
                else:
                    # Treat the entire object as a single item
                    data = [raw_data]
            
            # Ensure each item is a dictionary and add metadata
            result = []
            for item in data:
                if isinstance(item, dict):
                    # Add metadata
                    item['_api_source'] = 'ossinsight'
                    item['_endpoint'] = endpoint
                    result.append(item)
                else:
                    self.logger.warning(f"Skipping non-dict item in {endpoint}: {type(item)}")
            
            return result


def main_ossinsight():
    """Main function to run the ossinsight.io API client"""
    
    # Set up data directory
    data_dir = Path(__file__).parent.parent.parent / "data" / "ossinsight"
    
    # Create client
    client = OssinsightClient(data_dir)
    
    # Define endpoints to fetch based on OSS Insight API documentation
    endpoints = [
        {
            'endpoint': 'trends/repos/',
            'params': {
                'period': 'daily',
                'language': 'All'
            },
            'name': 'trending_daily_all'
        },
        {
            'endpoint': 'trends/repos/',
            'params': {
                'period': 'weekly',
                'language': 'All'
            },
            'name': 'trending_weekly_all'
        },
        {
            'endpoint': 'trends/repos/',
            'params': {
                'period': 'monthly',
                'language': 'Python'
            },
            'name': 'trending_monthly_python'
        },
        {
            'endpoint': 'repos/pingcap/tidb',  # Example repository
            'name': 'repo_pingcap_tidb'
        },
        {
            'endpoint': 'collections/',
            'name': 'collections_list'
        }
    ]
    
    # Run the client
    result = client.run(endpoints)
    
    if result:
        print(f"[SUCCESS] Ossinsight client completed successfully")
        print(f"  Data saved to: {result}")
        return 0
    else:
        print(f"[ERROR] Ossinsight client failed")
        return 1


if __name__ == "__main__":
    sys.exit(main_ossinsight())