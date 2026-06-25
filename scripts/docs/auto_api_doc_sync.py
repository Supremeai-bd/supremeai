#!/usr/bin/env python
"""
auto_api_doc_sync.py
====================
Automatically synchronizes FastAPI OpenAPI specification to documentation.

Fetches the OpenAPI JSON from the running SupremeAI API and converts it to
readable Markdown documentation for the docs/06-api/ folder.

Environment Variables:
- SUPREMEAI_API_URL: Base URL of the SupremeAI API (default: http://localhost:8000)
- OPENAPI_ENDPOINT: OpenAPI JSON endpoint (default: /openapi.json)
- OUTPUT_DIR: Directory to write markdown files (default: docs/06-api/)
- UPDATE_README: Whether to update the main README with API overview (default: true)
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
API_URL = os.getenv("SUPREMEAI_API_URL", "http://localhost:8000")
OPENAPI_ENDPOINT = os.getenv("OPENAPI_ENDPOINT", "/openapi.json")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "docs/06-api")
UPDATE_README = os.getenv("UPDATE_README", "true").lower() == "true"

def fetch_openapi_spec() -> Dict[str, Any]:
    """Fetch OpenAPI specification from the API."""
    url = f"{API_URL.rstrip('/')}{OPENAPI_ENDPOINT}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch OpenAPI spec from {url}: {e}")
        raise

def format_parameters(parameters: List[Dict]) -> str:
    """Format OpenAPI parameters into Markdown."""
    if not parameters:
        return ""
    
    md = "| Name | Location | Type | Required | Description |\n"
    md += "|------|----------|------|----------|-------------|\n"
    
    for param in parameters:
        name = param.get("name", "")
        location = param.get("in", "")
        schema = param.get("schema", {})
        param_type = schema.get("type", "string")
        required = "Yes" if param.get("required", False) else "No"
        description = param.get("description", "").replace("|", "\\|").replace("\n", " ")
        
        md += f"| {name} | {location} | {param_type} | {required} | {description} |\n"
    
    return md

def format_request_body(content: Dict) -> str:
    """Format OpenAPI request body into Markdown."""
    if not content:
        return ""
    
    # Handle JSON content primarily
    if "application/json" in content:
        schema = content["application/json"].get("schema", {})
        if schema:
            return f"```json\n{json.dumps(schema, indent=2)}\n```"
    
    return "_Request body content_"

def format_responses(responses: Dict) -> str:
    """Format OpenAPI responses into Markdown."""
    if not responses:
        return "_No documented responses_"
    
    md = ""
    for status_code, response in responses.items():
        description = response.get("description", "")
        content = response.get("content", {})
        
        md += f"### {status_code}\n\n"
        md += f"{description}\n\n"
        
        if content:
            media_type = list(content.keys())[0]  # Take first media type
            schema = content[media_type].get("schema", {})
            if schema:
                md += f"**{media_type}**:\n\n"
                md += f"```json\n{json.dumps(schema, indent=2)}\n```\n\n"
    
    return md

def generate_api_markdown(spec: Dict[str, Any]) -> str:
    """Generate Markdown documentation from OpenAPI spec."""
    info = spec.get("info", {})
    title = info.get("title", "SupremeAI API")
    version = info.get("version", "1.0.0")
    description = info.get("description", "")
    
    md = f"# {title} v{version}\n\n"
    md += f"{description}\n\n"
    md += f"*Generated automatically from OpenAPI specification*\n\n"
    md += "---\n\n"
    
    paths = spec.get("paths", {})
    if not paths:
        return md + "_No API paths documented._\n"
    
    # Group by tags for better organization
    tagged_paths = {}
    untagged_paths = []
    
    for path, path_item in paths.items():
        # Get tags from all operations in this path
        tags = set()
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                operation_tags = operation.get("tags", [])
                tags.update(operation_tags)
        
        # If no tags, put in "General" category
        if not tags:
            tags = {"General"}
        
        for tag in tags:
            if tag not in tagged_paths:
                tagged_paths[tag] = []
            tagged_paths[tag].append((path, path_item))
    
    # Sort tags alphabetically
    sorted_tags = sorted(tagged_paths.keys())
    
    for tag in sorted_tags:
        md += f"## {tag}\n\n"
        
        # Sort paths alphabetically within each tag
        tag_paths = sorted(tagged_paths[tag], key=lambda x: x[0])
        
        for path, path_item in tag_paths:
            md += f"### {path}\n\n"
            
            # Process each HTTP method
            for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                if method not in path_item:
                    continue
                
                operation = path_item[method]
                operation_id = operation.get("operationId", f"{method.upper()} {path}")
                summary = operation.get("summary", "")
                description = operation.get("description", "")
                
                md += f"#### {method.upper()} {path}\n\n"
                if summary:
                    md += f"**{summary}**\n\n"
                if description:
                    md += f"{description}\n\n"
                
                # Parameters
                parameters = operation.get("parameters", [])
                if parameters:
                    md += "**Parameters**\n\n"
                    md += format_parameters(parameters)
                    md += "\n"
                
                # Request Body
                request_body = operation.get("requestBody")
                if request_body:
                    md += "**Request Body**\n\n"
                    content = request_body.get("content", {})
                    md += format_request_body(content)
                    md += "\n\n"
                
                # Responses
                responses = operation.get("responses", {})
                if responses:
                    md += "**Responses**\n\n"
                    md += format_responses(responses)
                    md += "\n"
                
                md += "---\n\n"
    
    return md

def update_main_readme(api_md: str) -> None:
    """Update the main README.md with API documentation section."""
    readme_path = Path("README.md")
    if not readme_path.exists():
        logger.warning("README.md not found, skipping update")
        return
    
    try:
        content = readme_path.read_text(encoding="utf-8")
        
        # Look for API section markers
        start_marker = "<!-- API DOCS START -->"
        end_marker = "<!-- API DOCS END -->"
        
        if start_marker in content and end_marker in content:
            # Replace existing API section
            parts = content.split(start_marker)
            before = parts[0]
            after = parts[1].split(end_marker, 1)[1] if len(parts) > 1 else ""
            
            new_content = f"{before}{start_marker}\n\n{api_md}\n{end_marker}{after}"
            readme_path.write_text(new_content, encoding="utf-8")
            logger.info("Updated README.md with API documentation")
        else:
            # Append API section to end
            new_content = f"{content}\n\n<!-- API DOCS START -->\n\n{api_md}\n\n<!-- API DOCS END -->\n"
            readme_path.write_text(new_content, encoding="utf-8")
            logger.info("Added API documentation to README.md")
            
    except Exception as e:
        logger.error(f"Failed to update README.md: {e}")

def main() -> None:
    """Main function to synchronize API documentation."""
    print("🔄 Starting API documentation synchronization...")
    print(f"📡 Fetching OpenAPI spec from: {API_URL}{OPENAPI_ENDPOINT}")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    
    try:
        # Fetch OpenAPI specification
        spec = fetch_openapi_spec()
        print("✅ Successfully fetched OpenAPI specification")
        
        # Generate Markdown documentation
        api_markdown = generate_api_markdown(spec)
        
        # Ensure output directory exists
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Write API documentation file
        api_file = output_path / "api_reference.md"
        api_file.write_text(api_markdown, encoding="utf-8")
        print(f"✅ API documentation written to: {api_file}")
        
        # Optionally update main README
        if UPDATE_README:
            update_main_readme(api_markdown)
        
        print("🎉 API documentation synchronization completed successfully!")
        
    except Exception as e:
        print(f"❌ Failed to synchronize API documentation: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())