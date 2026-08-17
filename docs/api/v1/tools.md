# Tools API

## Overview

The Tools API provides endpoints for managing AI agent tools, executing tool operations, and registering custom tools. Tools are the building blocks that agents use to interact with external systems.

## Endpoints

### GET `/api/v1/tools`

List all available tools with their schemas.

**Response (200):**

```json
{
  "tools": [
    {
      "name": "web_search",
      "description": "Search the web for information",
      "parameters": {
        "query": { "type": "string", "required": true },
        "num_results": { "type": "integer", "required": false, "default": 5 }
      },
      "category": "search"
    },
    {
      "name": "code_interpreter",
      "description": "Execute Python code in a sandboxed environment",
      "parameters": {
        "code": { "type": "string", "required": true },
        "timeout": { "type": "integer", "required": false, "default": 30 }
      },
      "category": "execution"
    }
  ]
}
```

### POST `/api/v1/tools/execute`

Execute a tool with given parameters.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `tool_name` | string | Yes | Name of the tool to execute | `web_search` |
| `parameters` | object | Yes | Tool parameters | `{ "query": "latest AI news" }` |
| `timeout` | integer | No | Execution timeout in seconds | `30` |

**Response (200):**

```json
{
  "tool_name": "web_search",
  "result": {
    "results": [
      { "title": "AI Breakthrough...", "url": "https://...", "snippet": "..." }
    ]
  },
  "execution_time_ms": 1250
}
```

**Response (400):**

```json
{
  "error": "Invalid parameters for tool 'web_search'",
  "details": "Missing required parameter: query"
}
```

### POST `/api/v1/tools/register`

Register a new custom tool. Requires admin authentication.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `name` | string | Yes | Tool name (unique) | `custom_api` |
| `description` | string | Yes | Tool description | `Custom API integration` |
| `entry_point` | string | Yes | Python module path | `tools.custom.my_tool` |
| `parameters_schema` | object | Yes | JSON Schema for parameters | `{ "type": "object", ... }` |

**Response (201):**

```json
{
  "name": "custom_api",
  "status": "registered",
  "version": "1.0.0"
}
```

### GET `/api/v1/tools/categories`

List all tool categories.

**Response (200):**

```json
{
  "categories": [
    "search",
    "execution",
    "file_operations",
    "communication",
    "data_processing",
    "system",
    "ai_models"
  ]
}
```

## Tool Categories

| Category | Description | Example Tools |
|----------|-------------|---------------|
| `search` | Web and database search | web_search, database_query |
| `execution` | Code and command execution | code_interpreter, shell_exec |
| `file_operations` | File system operations | read_file, write_file, list_dir |
| `communication` | Email, Discord, messaging | email_agent, discord_bot |
| `data_processing` | Data analysis and transformation | csv_processor, json_parser |
| `system` | System monitoring and control | health_check, system_info |
| `ai_models` | AI model interactions | image_generator, text_summarizer |
