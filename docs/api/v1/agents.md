# Agents API

## Overview

The Agents API provides endpoints for managing AI agents, executing agent workflows, and monitoring agent performance. Agents can be autonomous (swarm orchestrator) or task-specific (browser, coding, research).

## Endpoints

### GET `/api/v1/agents`

List all available agents.

**Response (200):**

```json
{
  "agents": [
    {
      "id": "agent_001",
      "name": "Browser Agent",
      "type": "browser",
      "status": "active",
      "capabilities": ["web_scraping", "form_filling", "screenshot"]
    },
    {
      "id": "agent_002",
      "name": "Coding Agent",
      "type": "coding",
      "status": "active",
      "capabilities": ["code_generation", "refactoring", "debugging"]
    }
  ]
}
```

### POST `/api/v1/agents`

Create a new agent instance.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `name` | string | Yes | Agent name | `Research Agent` |
| `type` | string | Yes | Agent type | `research` |
| `config` | object | No | Agent configuration | `{ "model": "deepseek-coder" }` |

**Response (201):**

```json
{
  "id": "agent_003",
  "name": "Research Agent",
  "type": "research",
  "status": "initialized",
  "created_at": "2026-07-26T06:00:00Z"
}
```

### POST `/api/v1/agents/{agent_id}/execute`

Execute a task using a specific agent.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `agent_id` | string | Yes (path) | Agent identifier | `agent_001` |
| `task` | string | Yes | Task description | `Scrape the latest news from techcrunch.com` |
| `context` | object | No | Additional context | `{ "url": "https://techcrunch.com" }` |

**Response (200):**

```json
{
  "task_id": "task_abc123",
  "status": "running",
  "agent_id": "agent_001",
  "started_at": "2026-07-26T06:00:00Z"
}
```

### GET `/api/v1/agents/{agent_id}/status`

Get the status of a specific agent.

**Response (200):**

```json
{
  "id": "agent_001",
  "name": "Browser Agent",
  "status": "active",
  "last_activity": "2026-07-26T05:55:00Z",
  "tasks_completed": 42,
  "tasks_failed": 2
}
```

### POST `/api/v1/agents/{agent_id}/stop`

Stop a running agent.

**Response (200):**

```json
{
  "message": "Agent stopped successfully"
}
```

## Agent Types

| Type | Description | Key Capabilities |
|------|-------------|-----------------|
| `browser` | Web automation agent | Scraping, form filling, screenshots |
| `coding` | Code generation agent | Code gen, refactoring, debugging |
| `research` | Research agent | Web search, data analysis, synthesis |
| `email` | Email automation agent | Sending, reading, filtering emails |
| `github` | GitHub integration agent | PR management, issue tracking |
| `swarm` | Multi-agent orchestrator | Coordinates multiple agents |
