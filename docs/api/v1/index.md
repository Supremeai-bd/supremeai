# SupremeAI 2.0 API Documentation

Welcome to the SupremeAI 2.0 API documentation. This reference covers all available API endpoints for authentication, agents, tools, workflows, and webhooks.

## Base URL

```
https://supremeai-backend-08zd.onrender.com
```

For local development:

```
http://localhost:8000
```

## API Version

Current version: **v1**

All API endpoints are prefixed with `/api/v1/`.

## Authentication

All API requests require authentication via JWT tokens. See [Authentication](authentication.md) for details.

```bash
# Login to get access token
curl -X POST https://api.supremeai.dev/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "your_password"}'
```

## Rate Limiting

API requests are rate-limited to prevent abuse:

| Endpoint | Limit |
|----------|-------|
| Authentication | 10 requests/minute |
| Agent Execution | 30 requests/minute |
| Tool Execution | 60 requests/minute |
| General API | 100 requests/minute |

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": "Additional error details (optional)"
}
```

## Endpoints

| Category | Description |
|----------|-------------|
| [Authentication](authentication.md) | User login, logout, registration, token refresh |
| [Agents](agents.md) | Manage AI agents, execute tasks, monitor status |
| [Tools](tools.md) | Execute tools, register custom tools, list capabilities |
| [Workflows](workflows.md) | Create and execute multi-step agent workflows |
| [Webhooks](webhooks.md) | Manage webhook subscriptions and event notifications |

## Interactive Documentation

For interactive API testing, visit:

- **Swagger UI**: `https://api.supremeai.dev/docs`
- **ReDoc**: `https://api.supremeai.dev/redoc`

## SDK and Libraries

- **Python**: `pip install supremeai-sdk`
- **JavaScript**: `npm install @supremeai/sdk`
- **Postman Collection**: Download from [postman_collection.json](postman_collection.json)

## Support

- **Discord**: [SupremeAI Community](https://discord.gg/supremeai)
- **Email**: api-support@supremeai.dev
- **GitHub Issues**: [Report API issues](https://github.com/SaifulHaqueNiloy/supremeai/issues)
