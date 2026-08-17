# Workflows API

## Overview

The Workflows API provides endpoints for managing and executing multi-step agent workflows. Workflows orchestrate multiple agents and tools to accomplish complex tasks through defined sequences.

## Endpoints

### GET `/api/v1/workflows`

List all available workflows.

**Response (200):**

```json
{
  "workflows": [
    {
      "id": "wf_001",
      "name": "Code Review Pipeline",
      "description": "Automated code review with security scanning",
      "steps": 5,
      "status": "active"
    },
    {
      "id": "wf_002",
      "name": "Content Generation",
      "description": "Multi-agent content creation and editing",
      "steps": 3,
      "status": "active"
    }
  ]
}
```

### POST `/api/v1/workflows`

Create a new workflow definition.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `name` | string | Yes | Workflow name | `Bug Triage` |
| `description` | string | Yes | Workflow description | `Automatically triage and assign bugs` |
| `steps` | array | Yes | Ordered list of step definitions | `[{ "agent": "research", "task": "..." }]` |

**Response (201):**

```json
{
  "id": "wf_003",
  "name": "Bug Triage",
  "description": "Automatically triage and assign bugs",
  "steps": 3,
  "status": "draft",
  "created_at": "2026-07-26T06:00:00Z"
}
```

### POST `/api/v1/workflows/{workflow_id}/execute`

Execute a workflow with given input.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `workflow_id` | string | Yes (path) | Workflow identifier | `wf_001` |
| `input` | object | Yes | Input data for the workflow | `{ "repo_url": "https://github.com/..." }` |
| `config` | object | No | Execution configuration | `{ "timeout": 300 }` |

**Response (202):**

```json
{
  "execution_id": "exec_abc123",
  "workflow_id": "wf_001",
  "status": "running",
  "started_at": "2026-07-26T06:00:00Z"
}
```

### GET `/api/v1/workflows/{workflow_id}/executions`

List execution history for a workflow.

**Response (200):**

```json
{
  "executions": [
    {
      "id": "exec_abc123",
      "status": "completed",
      "started_at": "2026-07-26T05:00:00Z",
      "completed_at": "2026-07-26T05:05:00Z",
      "duration_ms": 300000
    }
  ]
}
```

### GET `/api/v1/workflows/{workflow_id}/executions/{execution_id}`

Get detailed status of a specific workflow execution.

**Response (200):**

```json
{
  "id": "exec_abc123",
  "workflow_id": "wf_001",
  "status": "completed",
  "started_at": "2026-07-26T05:00:00Z",
  "completed_at": "2026-07-26T05:05:00Z",
  "duration_ms": 300000,
  "steps": [
    { "step": 1, "agent": "research", "status": "completed", "output": "..." },
    { "step": 2, "agent": "coding", "status": "completed", "output": "..." }
  ]
}
```

## Workflow Step Format

Each step in a workflow definition follows this schema:

```json
{
  "agent": "string",
  "task": "string",
  "context": "object",
  "timeout": "integer",
  "on_failure": "continue|stop|retry"
}
```
