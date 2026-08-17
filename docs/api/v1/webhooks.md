# Webhooks API

## Overview

The Webhooks API provides endpoints for managing webhook subscriptions and receiving event notifications. Webhooks allow external systems to receive real-time updates about events in SupremeAI.

## Endpoints

### GET `/api/v1/webhooks`

List all webhook subscriptions.

**Response (200):**

```json
{
  "webhooks": [
    {
      "id": "wh_001",
      "url": "https://example.com/webhook",
      "events": ["agent.completed", "workflow.failed"],
      "status": "active",
      "created_at": "2026-07-26T06:00:00Z"
    }
  ]
}
```

### POST `/api/v1/webhooks`

Create a new webhook subscription.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `url` | string | Yes | Webhook endpoint URL | `https://example.com/webhook` |
| `events` | array | Yes | List of event types to subscribe to | `["agent.completed", "workflow.started"]` |
| `secret` | string | No | Secret for signature verification | `my_webhook_secret` |

**Response (201):**

```json
{
  "id": "wh_002",
  "url": "https://example.com/webhook",
  "events": ["agent.completed", "workflow.started"],
  "status": "active",
  "created_at": "2026-07-26T06:00:00Z"
}
```

### DELETE `/api/v1/webhooks/{webhook_id}`

Delete a webhook subscription.

**Response (204):** No content

### POST `/api/v1/webhooks/{webhook_id}/test`

Send a test event to a webhook subscription.

**Response (200):**

```json
{
  "message": "Test event sent successfully",
  "event_id": "evt_test_123"
}
```

## Available Events

| Event | Description |
|-------|-------------|
| `agent.started` | An agent execution has started |
| `agent.completed` | An agent execution has completed |
| `agent.failed` | An agent execution has failed |
| `workflow.started` | A workflow execution has started |
| `workflow.completed` | A workflow execution has completed |
| `workflow.failed` | A workflow execution has failed |
| `tool.executed` | A tool has been executed |
| `billing.payment_succeeded` | A payment was successful |
| `billing.payment_failed` | A payment failed |

## Webhook Payload Format

All webhook payloads include the following structure:

```json
{
  "event_id": "evt_123",
  "event_type": "agent.completed",
  "timestamp": "2026-07-26T06:00:00Z",
  "data": {
    // Event-specific data
  },
  "signature": "sha256_hmac_signature"
}
```

## Security

- Webhooks support HMAC signature verification using the provided secret
- The `X-SupremeAI-Signature` header contains the HMAC-SHA256 signature
- Failed webhook deliveries are retried with exponential backoff (max 5 retries)
- Webhook endpoints must respond with HTTP 200 within 30 seconds
