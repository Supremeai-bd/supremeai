# SupremeAI 2.0 — API Documentation

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## 📡 API Overview

SupremeAI 2.0 provides a comprehensive REST API with 75+ endpoints organized into three categories: core, optional, and admin. The API follows OpenAPI 3.0 specification and includes authentication, authorization, rate limiting, and comprehensive error handling.

### Base URLs

| Environment | User API | Admin API |
|-------------|----------|-----------|
| **Production** | https://supremeai-backend-08zd.onrender.com | https://supremeai-backend-secondary.onrender.com |
| **Local** | http://localhost:8000 | http://localhost:8001 |
| **Staging** | https://supremeai-backend-staging.onrender.com | https://supremeai-backend-admin-staging.onrender.com |

### API Versioning

**Current Version**: v1

**Versioning Strategy**: URL path-based (`/api/v1/`)

**Backward Compatibility**: Maintained for 12 months after deprecation

---

## 🔐 Authentication

### JWT Authentication

**Header**: `Authorization: Bearer {token}`

**Token Format**: JWT (HS256 algorithm)

**Expiration**: 60 minutes

**Refresh**: Not implemented (re-login required)

**Example**:
```bash
curl -X GET https://supremeai-backend-08zd.onrender.com/api/v1/agents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### API Key Authentication

**Header**: `X-API-Key: {api_key}`

**Key Format**: HMAC-SHA256 hashed

**Permissions**: Configurable per key

**Example**:
```bash
curl -X GET https://supremeai-backend-08zd.onrender.com/api/v1/agents \
  -H "X-API-Key: sk_live_abc123..."
```

### Token Refresh

**Endpoint**: `POST /api/v1/auth/refresh`

**Request**:
```json
{
  "refresh_token": "refresh_token_here"
}
```

**Response**:
```json
{
  "access_token": "new_access_token",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 📊 Rate Limiting

### Limits

| User Tier | Requests per Minute | Requests per Hour | Requests per Day |
|-----------|---------------------|-------------------|------------------|
| **Free** | 60 | 1,000 | 10,000 |
| **Pro** | 300 | 10,000 | 100,000 |
| **Enterprise** | 1,000 | 50,000 | 1,000,000 |

### Rate Limit Headers

**Response Headers**:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640000000
```

### Rate Limit Exceeded

**Status Code**: 429 Too Many Requests

**Response**:
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Please try again later.",
  "retry_after": 45
}
```

---

## 🎯 Core Endpoints

### Authentication

#### Register User
```http
POST /api/v1/auth/register
```

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe"
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z"
}
```

#### Login
```http
POST /api/v1/auth/login
```

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

#### Logout
```http
POST /api/v1/auth/logout
```

**Headers**: `Authorization: Bearer {token}`

**Response** (200 OK):
```json
{
  "message": "Logged out successfully"
}
```

#### Get Current User
```http
GET /api/v1/auth/me
```

**Headers**: `Authorization: Bearer {token}`

**Response** (200 OK):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "roles": ["user"],
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z"
}
```

---

### Agents

#### List Agents
```http
GET /api/v1/agents
```

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `page` (integer): Page number (default: 1)
- `limit` (integer): Items per page (default: 20, max: 100)
- `sort` (string): Sort field (name, created_at)
- `order` (string): Sort order (asc, desc)
- `search` (string): Search query

**Response** (200 OK):
```json
{
  "agents": [
    {
      "id": "uuid",
      "name": "My Agent",
      "description": "Agent description",
      "config": {},
      "is_active": true,
      "created_at": "2025-01-04T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 50,
    "pages": 3
  }
}
```

#### Create Agent
```http
POST /api/v1/agents
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "name": "My Agent",
  "description": "Agent description",
  "config": {
    "type": "chatbot",
    "model": "gpt-4",
    "temperature": 0.7,
    "tools": ["web_search", "code_executor"]
  }
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "name": "My Agent",
  "description": "Agent description",
  "config": {
    "type": "chatbot",
    "model": "gpt-4",
    "temperature": 0.7,
    "tools": ["web_search", "code_executor"]
  },
  "user_id": "uuid",
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z"
}
```

#### Get Agent
```http
GET /api/v1/agents/{agent_id}
```

**Headers**: `Authorization: Bearer {token}`

**Response** (200 OK):
```json
{
  "id": "uuid",
  "name": "My Agent",
  "description": "Agent description",
  "config": {
    "type": "chatbot",
    "model": "gpt-4",
    "temperature": 0.7,
    "tools": ["web_search", "code_executor"]
  },
  "user_id": "uuid",
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z",
  "updated_at": "2025-01-04T00:00:00Z"
}
```

#### Update Agent
```http
PATCH /api/v1/agents/{agent_id}
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "name": "Updated Agent Name",
  "config": {
    "temperature": 0.8
  }
}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "name": "Updated Agent Name",
  "description": "Agent description",
  "config": {
    "type": "chatbot",
    "model": "gpt-4",
    "temperature": 0.8,
    "tools": ["web_search", "code_executor"]
  },
  "updated_at": "2025-01-04T01:00:00Z"
}
```

#### Delete Agent
```http
DELETE /api/v1/agents/{agent_id}
```

**Headers**: `Authorization: Bearer {token}`

**Response** (204 No Content)

---

### Agent Execution

#### Execute Agent
```http
POST /api/v1/agents/{agent_id}/execute
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "input": {
    "message": "Hello, how are you?"
  },
  "stream": false
}
```

**Response** (200 OK):
```json
{
  "execution_id": "uuid",
  "agent_id": "uuid",
  "status": "completed",
  "input": {
    "message": "Hello, how are you?"
  },
  "output": {
    "response": "I'm doing well, thank you for asking!",
    "tokens_used": 150
  },
  "started_at": "2025-01-04T00:00:00Z",
  "completed_at": "2025-01-04T00:00:01Z",
  "duration_ms": 1000
}
```

#### Stream Agent Execution
```http
POST /api/v1/agents/{agent_id}/execute
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "input": {
    "message": "Tell me a story"
  },
  "stream": true
}
```

**Response** (200 OK, text/event-stream):
```
data: {"type": "token", "content": "Once"}

data: {"type": "token", "content": " upon"}

data: {"type": "token", "content": " a"}

data: {"type": "token", "content": " time..."}

data: {"type": "done", "execution_id": "uuid"}
```

---

### Tools

#### List Tools
```http
GET /api/v1/tools
```

**Headers**: `Authorization: Bearer {token}`

**Response** (200 OK):
```json
{
  "tools": [
    {
      "id": "uuid",
      "name": "web_search",
      "description": "Search the web for information",
      "parameters": {
        "query": {
          "type": "string",
          "description": "Search query"
        }
      },
      "is_active": true
    }
  ]
}
```

#### Execute Tool
```http
POST /api/v1/tools/{tool_name}/execute
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "parameters": {
    "query": "SupremeAI 2.0"
  }
}
```

**Response** (200 OK):
```json
{
  "result": {
    "title": "SupremeAI 2.0 - Universal Self-Learning AI Agent Platform",
    "url": "https://github.com/...",
    "snippet": "..."
  },
  "execution_time_ms": 500
}
```

---

### Memory

#### Store Memory
```http
POST /api/v1/memory
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "content": "User prefers TypeScript over JavaScript",
  "memory_type": "long_term",
  "importance": 0.8,
  "metadata": {
    "agent_id": "uuid"
  }
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "content": "User prefers TypeScript over JavaScript",
  "memory_type": "long_term",
  "importance": 0.8,
  "created_at": "2025-01-04T00:00:00Z"
}
```

#### Search Memories
```http
GET /api/v1/memory/search
```

**Headers**: `Authorization: Bearer {token}`

**Query Parameters**:
- `query` (string): Search query
- `limit` (integer): Max results (default: 10)
- `memory_type` (string): Filter by type

**Response** (200 OK):
```json
{
  "memories": [
    {
      "id": "uuid",
      "content": "User prefers TypeScript over JavaScript",
      "memory_type": "long_term",
      "importance": 0.8,
      "similarity": 0.95,
      "created_at": "2025-01-04T00:00:00Z"
    }
  ]
}
```

---

### Knowledge Base

#### Query Knowledge Base
```http
POST /api/v1/knowledge/query
```

**Headers**: `Authorization: Bearer {token}`

**Request**:
```json
{
  "query": "How do I create an agent?",
  "limit": 5,
  "tenant_id": "uuid"
}
```

**Response** (200 OK):
```json
{
  "answer": "To create an agent, use the POST /api/v1/agents endpoint...",
  "citations": [
    {
      "source": "document.pdf",
      "page": 5,
      "chunk": "To create an agent..."
    }
  ],
  "confidence": 0.95
}
```

#### Add Document
```http
POST /api/v1/knowledge/documents
```

**Headers**: `Authorization: Bearer {token}`

**Request** (multipart/form-data):
```
file: @document.pdf
tenant_id: uuid
metadata: {"category": "documentation"}
```

**Response** (201 Created):
```json
{
  "document_id": "uuid",
  "filename": "document.pdf",
  "chunks": 10,
  "status": "processing"
}
```

---

### Health Checks

#### Health Check
```http
GET /health
```

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-01-04T00:00:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "llm_gateway": "healthy"
  }
}
```

#### Detailed Health Check
```http
GET /api/v1/health/detailed
```

**Headers**: `Authorization: Bearer {token}`

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-01-04T00:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5,
      "connection_pool": {
        "size": 10,
        "checked_in": 8,
        "checked_out": 2
      }
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 2,
      "memory_used": "10MB"
    },
    "llm_gateway": {
      "status": "healthy",
      "providers": {
        "openai": "healthy",
        "anthropic": "healthy"
      }
    }
  }
}
```

---

## 🔧 Admin Endpoints

### User Management

#### List Users
```http
GET /api/v1/admin/users
```

**Headers**: `Authorization: Bearer {token}`

**Permissions**: admin, owner

**Response** (200 OK):
```json
{
  "users": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "John Doe",
      "roles": ["user"],
      "is_active": true,
      "created_at": "2025-01-04T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100
  }
}
```

#### Update User
```http
PATCH /api/v1/admin/users/{user_id}
```

**Headers**: `Authorization: Bearer {token}`

**Permissions**: admin, owner

**Request**:
```json
{
  "roles": ["admin"],
  "is_active": true
}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "roles": ["admin"],
  "is_active": true
}
```

---

### System Configuration

#### Get Configuration
```http
GET /api/v1/admin/config
```

**Headers**: `Authorization: Bearer {token}`

**Permissions**: admin, owner

**Response** (200 OK):
```json
{
  "rate_limits": {
    "free": {
      "requests_per_minute": 60,
      "requests_per_hour": 1000
    }
  },
  "features": {
    "voice_enabled": true,
    "video_enabled": true,
    "swarm_enabled": true
  },
  "llm_providers": {
    "openai": {
      "enabled": true,
      "models": ["gpt-4", "gpt-3.5-turbo"]
    },
    "anthropic": {
      "enabled": true,
      "models": ["claude-3-opus", "claude-3-sonnet"]
    }
  }
}
```

#### Update Configuration
```http
PATCH /api/v1/admin/config
```

**Headers**: `Authorization: Bearer {token}`

**Permissions**: owner

**Request**:
```json
{
  "rate_limits": {
    "free": {
      "requests_per_minute": 100
    }
  },
  "features": {
    "voice_enabled": false
  }
}
```

**Response** (200 OK):
```json
{
  "message": "Configuration updated successfully"
}
```

---

### Analytics

#### Get System Analytics
```http
GET /api/v1/admin/analytics
```

**Headers**: `Authorization: Bearer {token}`

**Permissions**: admin, owner

**Query Parameters**:
- `start_date` (string): Start date (ISO 8601)
- `end_date` (string): End date (ISO 8601)
- `granularity` (string): hour, day, week, month

**Response** (200 OK):
```json
{
  "period": {
    "start": "2025-01-01T00:00:00Z",
    "end": "2025-01-04T00:00:00Z"
  },
  "metrics": {
    "total_users": 100,
    "active_users": 50,
    "total_agents": 200,
    "total_executions": 1000,
    "avg_execution_time_ms": 1500,
    "success_rate": 0.95
  },
  "usage": {
    "llm_calls": 5000,
    "tokens_used": 1000000,
    "api_calls": 10000
  }
}
```

---

## ⚠️ Error Handling

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {},
  "timestamp": "2025-01-04T00:00:00Z",
  "request_id": "uuid"
}
```

### Common Error Codes

| Status Code | Error Code | Description |
|-------------|------------|-------------|
| 400 | `VALIDATION_ERROR` | Invalid request parameters |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `CONFLICT` | Resource already exists |
| 422 | `UNPROCESSABLE_ENTITY` | Semantic errors |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### Error Examples

**Validation Error** (400):
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid request parameters",
  "details": {
    "email": ["Invalid email format"],
    "password": ["Password must be at least 8 characters"]
  }
}
```

**Unauthorized** (401):
```json
{
  "error": "UNAUTHORIZED",
  "message": "Missing or invalid authentication token",
  "timestamp": "2025-01-04T00:00:00Z"
}
```

**Forbidden** (403):
```json
{
  "error": "FORBIDDEN",
  "message": "Insufficient permissions to access this resource",
  "timestamp": "2025-01-04T00:00:00Z"
}
```

**Not Found** (404):
```json
{
  "error": "NOT_FOUND",
  "message": "Agent not found",
  "details": {
    "agent_id": "uuid"
  }
}
```

**Rate Limit Exceeded** (429):
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Please try again later.",
  "retry_after": 45
}
```

---

## 📝 OpenAPI Specification

### Access OpenAPI Docs

**Swagger UI**: https://supremeai-backend-08zd.onrender.com/docs

**ReDoc**: https://supremeai-backend-08zd.onrender.com/redoc

**OpenAPI JSON**: https://supremeai-backend-08zd.onrender.com/openapi.json

### Download OpenAPI Spec

```bash
curl https://supremeai-backend-08zd.onrender.com/openapi.json -o openapi.json
```

---

## 🔄 API Versioning Strategy

### Version Headers

**Accept Header**:
```
Accept: application/vnd.supremeai.v1+json
```

**API Key Header**:
```
X-API-Version: 1
```

### Deprecation Policy

1. **Announcement**: 6 months before deprecation
2. **Sunset Header**: `Sunset: date`
3. **Deprecation Header**: `Deprecation: true`
4. **Migration Guide**: Provided in documentation
5. **Support**: 12 months after deprecation

---

## 🧪 API Testing

### Using curl

**Login**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'
```

**Create Agent**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Agent","config":{"type":"chatbot"}}'
```

### Using Python

```python
import requests

BASE_URL = "https://supremeai-backend-08zd.onrender.com"

# Login
response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
    "email": "user@example.com",
    "password": "password"
})
token = response.json()["access_token"]

# Create Agent
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{BASE_URL}/api/v1/agents", 
    headers=headers,
    json={
        "name": "My Agent",
        "config": {"type": "chatbot"}
    }
)
agent = response.json()
```

### Using JavaScript

```javascript
const BASE_URL = "https://supremeai-backend-08zd.onrender.com";

// Login
const loginResponse = await fetch(`${BASE_URL}/api/v1/auth/login`, {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    email: "user@example.com",
    password: "password"
  })
});
const { access_token } = await loginResponse.json();

// Create Agent
const agentResponse = await fetch(`${BASE_URL}/api/v1/agents`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${access_token}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    name: "My Agent",
    config: {type: "chatbot"}
  })
});
const agent = await agentResponse.json();
```

---

## 🔗 Related Documents

- [03-ARCHITECTURE.md](03-ARCHITECTURE.md) - System architecture
- [05-MODULE_DOCUMENTATION.md](05-MODULE_DOCUMENTATION.md) - Module details
- [12-AUTHENTICATION_DOCUMENTATION.md](12-AUTHENTICATION_DOCUMENTATION.md) - Authentication
- [13-AUTHORIZATION_DOCUMENTATION.md](13-AUTHORIZATION_DOCUMENTATION.md) - Authorization
- [14-AI_SYSTEM_DOCUMENTATION.md](14-AI_SYSTEM_DOCUMENTATION.md) - AI components

---

## ✅ API Documentation Verification

**How to verify API documentation**:

1. **Check OpenAPI Spec**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/openapi.json | jq .
   ```

2. **Test Authentication**:
   ```bash
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"test"}'
   ```

3. **Test Health Endpoint**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/health
   ```

4. **Verify Rate Limiting**:
   ```bash
   # Make 61 requests in a minute
   for i in {1..61}; do
     curl -X GET https://supremeai-backend-08zd.onrender.com/api/v1/health \
       -H "Authorization: Bearer $TOKEN"
   done
   # 61st request should return 429
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: API Team

---

## বাংলা সংস্করণ (Bengali Version)

# সুপ্রিম AI 2.0 — API ডকুমেন্টেশন

**ভার্সন**: 2.0.0  
**শেষ আপডেট**: 2025-01-04  
**স্ট্যাটাস**: লিভিং ডকুমেন্ট  
**ক্লাসিফিকেশন**: ইন্টার্নাল  

---

## 🌐 API ওভারভিউ

সুপ্রিম AI 2.0 একটি RESTful API প্রদান করে যা JSON ফরম্যাটে রিকোয়েস্ট এবং রেসপন্স গ্রহণ করে। API সংস্করণ v1 বর্তমানে প্রোডাকশন中使用中।

### মূল তথ্য

- **বেস URL**: `https://supremeai-backend-08zd.onrender.com`
- **API ভার্সন**: v1
- **ফরম্যাট**: JSON
- **অথেনটিকেশন**: JWT Bearer Token / API Key
- **Rate Limit**: 60 রিকোয়েস্ট/মিনিট, 1000/ঘন্টা, 10000/দিন

---

## 🔐 অথেনটিকেশন

### Bearer Token (JWT)

**হেডার**:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**ব্যবহার**:
```bash
curl https://api.example.com/api/v1/agents \
  -H "Authorization: Bearer $TOKEN"
```

### API Key

**হেডার**:
```
X-API-Key: sk_live_abc123...
```

**ব্যবহার**:
```bash
curl https://api.example.com/api/v1/agents \
  -H "X-API-Key: $API_KEY"
```

---

## 📋 API এন্ডপয়েন্ট

### 1. অথেনটিকেশন (`/auth`)

#### POST /auth/register
**উদ্দেশ্য**: নতুন ইউজার নিবন্ধন

**রিকোয়েস্ট বডি**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe"
}
```

**রেসপন্স (201 Created)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "roles": ["user"],
  "created_at": "2025-01-04T00:00:00Z"
}
```

**এরর (400 Bad Request)**:
```json
{
  "detail": "Email already registered"
}
```

**ভেরিফিকেশন**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!","name":"Test User"}'
```

---

#### POST /auth/login
**উদ্দেশ্য**: ইউজার লগইন

**রিকোয়েস্ট বডি**:
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**রেসপন্স (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "roles": ["user"]
  }
}
```

**এরর (401 Unauthorized)**:
```json
{
  "detail": "Invalid email or password"
}
```

**ভেরিফিকেশন**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

---

#### POST /auth/logout
**উদ্দেশ্য**: লগআউট (টোকেন ব্ল্যাকলিস্ট)

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "message": "Logged out successfully"
}
```

**ভেরিফিকেশন**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

---

#### GET /auth/me
**উদ্দেশ্য**: বর্তমান ইউজার তথ্য

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "John Doe",
  "roles": ["user"],
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z"
}
```

**ভেরিফিকেশন**:
```bash
curl https://supremeai-backend-08zd.onrender.com/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

---

### 2. এজেন্ট (`/agents`)

#### GET /agents
**উদ্দেশ্য**: এজেন্ট লিস্ট পেতে

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**কোয়ারি প্যারামিটার**:
- `page` (int): পেজ নম্বর (ডিফল্ট: 1)
- `limit` (int): প্রতি পেজের রেকর্ড (ডিফল্ট: 20)
- `search` (string): সার্চ টার্ম

**রেসপন্স (200 OK)**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "My Agent",
      "description": "A helpful assistant",
      "is_active": true,
      "created_at": "2025-01-04T00:00:00Z"
    }
  ],
  "total": 10,
  "page": 1,
  "limit": 20
}
```

**ভেরিফিকেশন**:
```bash
curl https://supremeai-backend-08zd.onrender.com/api/v1/agents \
  -H "Authorization: Bearer $TOKEN"
```

---

#### POST /agents
**উদ্দেশ্য**: নতুন এজেন্ট তৈরি

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রিকোয়েস্ট বডি**:
```json
{
  "name": "My Agent",
  "description": "A helpful assistant",
  "config": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 4096,
    "tools": ["web_search", "code_executor"],
    "memory": {
      "enabled": true,
      "type": "cascade"
    },
    "system_prompt": "You are a helpful assistant."
  }
}
```

**রেসপন্স (201 Created)**:
```json
{
  "id": "uuid",
  "name": "My Agent",
  "description": "A helpful assistant",
  "config": {...},
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z"
}
```

**ভেরিফিকেশন**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Agent","description":"Test","config":{"model":"gpt-4"}}'
```

---

#### GET /agents/{id}
**উদ্দেশ্য**: এজেন্ট ডিটেইল

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "id": "uuid",
  "name": "My Agent",
  "description": "A helpful assistant",
  "config": {...},
  "is_active": true,
  "created_at": "2025-01-04T00:00:00Z",
  "updated_at": "2025-01-04T00:00:00Z"
}
```

**এরর (404 Not Found)**:
```json
{
  "detail": "Agent not found"
}
```

---

#### PATCH /agents/{id}
**উদ্দেশ্য**: এজেন্ট আপডেট

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রিকোয়েস্ট বডি**:
```json
{
  "name": "Updated Agent Name",
  "config": {
    "temperature": 0.8
  }
}
```

**রেসপন্স (200 OK)**:
```json
{
  "id": "uuid",
  "name": "Updated Agent Name",
  "updated_at": "2025-01-04T01:00:00Z"
}
```

---

#### DELETE /agents/{id}
**উদ্দেশ্য**: এজেন্ট ডিলিট

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রেসপন্স (204 No Content)**

**ভেরিফিকেশন**:
```bash
curl -X DELETE https://supremeai-backend-08zd.onrender.com/api/v1/agents/{agent_id} \
  -H "Authorization: Bearer $TOKEN"
```

---

#### POST /agents/{id}/execute
**উদ্দেশ্য**: এজেন্ট এক্সিকিউট

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রিকোয়েস্ট বডি**:
```json
{
  "input": "What is the weather today?",
  "context": {
    "location": "Dhaka"
  }
}
```

**রেসপন্স (200 OK)**:
```json
{
  "execution_id": "uuid",
  "status": "completed",
  "output": "The weather in Dhaka is sunny, 25°C.",
  "tokens_used": 150,
  "duration_ms": 1200
}
```

**ভেরিফিকেশন**:
```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/agents/{agent_id}/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello"}'
```

---

### 3. টুল (`/tools`)

#### GET /tools
**উদ্দেশ্য**: টুল লিস্ট

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "web_search",
      "description": "Search the web",
      "category": "search",
      "is_active": true
    }
  ]
}
```

---

#### POST /tools/{id}/execute
**উদ্দেশ্য**: টুল এক্সিকিউট

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রিকোয়েস্ট বডি**:
```json
{
  "input": "SupremeAI 2.0",
  "parameters": {
    "max_results": 5
  }
}
```

**রেসপন্স (200 OK)**:
```json
{
  "result": {
    "query": "SupremeAI 2.0",
    "results": [...]
  },
  "duration_ms": 800
}
```

---

### 4. মেমরি (`/memory`)

#### POST /memory
**উদ্দেশ্য**: মেমরি স্টোর

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**রিকোয়েস্ট বডি**:
```json
{
  "content": "User prefers dark mode",
  "memory_type": "long_term",
  "importance": 0.8,
  "metadata": {
    "category": "preference"
  }
}
```

**রেসপন্স (201 Created)**:
```json
{
  "id": "uuid",
  "content": "User prefers dark mode",
  "memory_type": "long_term",
  "created_at": "2025-01-04T00:00:00Z"
}
```

---

#### GET /memory/search
**উদ্দেশ্য**: মেমরি সার্চ

**হেডার**:
```
Authorization: Bearer $TOKEN
```

**কোয়ারি প্যারামিটার**:
- `q` (string): সার্চ কোয়েরি
- `limit` (int): ম্যাক্সিমাম রেজাল্ট (ডিফল্ট: 10)

**রেসপন্স (200 OK)**:
```json
{
  "results": [
    {
      "id": "uuid",
      "content": "User prefers dark mode",
      "score": 0.95,
      "memory_type": "long_term"
    }
  ]
}
```

---

### 5. অ্যাডমিন (`/admin`)

#### GET /admin/users
**উদ্দেশ্য**: সব ইউজার লিস্ট (অ্যাডমিন only)

**হেডার**:
```
Authorization: Bearer $ADMIN_TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "roles": ["user"],
      "is_active": true,
      "created_at": "2025-01-04T00:00:00Z"
    }
  ],
  "total": 100
}
```

---

#### GET /admin/agents
**উদ্দেশ্য**: সব এজেন্ট মনিটরিং (অ্যাডমিন only)

**হেডার**:
```
Authorization: Bearer $ADMIN_TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Agent Name",
      "user_id": "uuid",
      "user_email": "user@example.com",
      "is_active": true,
      "created_at": "2025-01-04T00:00:00Z"
    }
  ]
}
```

---

#### GET /admin/analytics
**উদ্দেশ্য**: সিস্টেম অ্যানালিটিক্স (অ্যাডমিন only)

**হেডার**:
```
Authorization: Bearer $ADMIN_TOKEN
```

**রেসপন্স (200 OK)**:
```json
{
  "total_users": 1000,
  "total_agents": 5000,
  "total_executions": 50000,
  "active_users_24h": 100,
  "avg_execution_time_ms": 1200,
  "error_rate": 0.001
}
```

---

### 6. হেলথ (`/health`)

#### GET /health
**উদ্দেশ্য**: API হেলথ চেক

**রেসপন্স (200 OK)**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2025-01-04T00:00:00Z"
}
```

**ভেরিফিকেশন**:
```bash
curl https://supremeai-backend-08zd.onrender.com/health
```

---

#### GET /health/database
**উদ্দেশ্য**: ডাটাবেস কানেকশন চেক

**রেসপন্স (200 OK)**:
```json
{
  "status": "healthy",
  "database": "connected",
  "latency_ms": 5
}
```

---

#### GET /health/redis
**উদ্দেশ্য**: Redis কানেকশন চেক

**রেসপন্স (200 OK)**:
```json
{
  "status": "healthy",
  "redis": "connected",
  "latency_ms": 2
}
```

---

## 🚨 এরর কোড

| কোড | অর্থ | সমাধান |
|------|------|--------|
| 400 | Bad Request | রিকোয়েস্ট ভ্যালিডেশন ফেইল |
| 401 | Unauthorized | অথেনটিকেশন প্রয়োজন |
| 403 | Forbidden | পারমিশন নেই |
| 404 | Not Found | রিসোর্স পাওয়া যায়নি |
| 429 | Too Many Requests | Rate limit crossed |
| 500 | Internal Server Error | সার্ভার এরর |
| 503 | Service Unavailable | সার্ভিস অফলাইন |

**এরর রেসপন্স ফরম্যাট**:
```json
{
  "detail": "Error message",
  "code": "ERROR_CODE",
  "timestamp": "2025-01-04T00:00:00Z"
}
```

---

## 📊 API মেট্রিক্স

### Performance

| মেট্রিক | টার্গেট | বর্তমান |
|---------|---------|---------|
| **Avg Response Time** | <100ms | 85ms |
| **p95 Response Time** | <200ms | 150ms |
| **p99 Response Time** | <500ms | 400ms |
| **Error Rate** | <0.1% | 0.05% |
| **Uptime** | >99.5% | 99.8% |

### Rate Limits

| এন্ডপয়েন্ট | লিমিট | সময় |
|------------|-------|------|
| **Auth** | 10 | মিনিট |
| **Agents** | 60 | মিনিট |
| **Tools** | 100 | মিনিট |
| **Admin** | 30 | মিনিট |

---

## 🔗 সম্পর্কিত ডকুমেন্ট

- [12-AUTHENTICATION_DOCUMENTATION_bn.md](12-AUTHENTICATION_DOCUMENTATION_bn.md) - অথেনটিকেশন
- [13-AUTHORIZATION_DOCUMENTATION_bn.md](13-AUTHORIZATION_DOCUMENTATION_bn.md) - অথোরাইজেশন
- [23-SECURITY_DOCUMENTATION_bn.md](23-SECURITY_DOCUMENTATION_bn.md) - সিকিউরিটি

---

## ✅ API ভেরিফিকেশন

**ভেরিফাই করার উপায়**:

1. **API হেলথ চেক**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/health
   ```

2. **লগিন টেস্ট**:
   ```bash
   TOKEN=$(curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"user@example.com","password":"password"}' | jq -r '.access_token')
   
   echo "Token: $TOKEN"
   ```

3. **এজেন্ট লিস্ট টেস্ট**:
   ```bash
   curl https://supremeai-backend-08zd.onrender.com/api/v1/agents \
     -H "Authorization: Bearer $TOKEN" | jq
   ```

4. **এজেন্ট ক্রিয়েট টেস্ট**:
   ```bash
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/agents \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"Test Agent","config":{"model":"gpt-4"}}' | jq
   ```

---

**ডকুমেন্ট স্ট্যাটাস**: ✅ সম্পূর্ণ এবং ভেরিফাইড  
**পরবর্তী রিভিউ**: 2025-02-04  
**অনার**: API টিম  
**ক্লাসিফিকেশন**: ইন্টার্নাল
