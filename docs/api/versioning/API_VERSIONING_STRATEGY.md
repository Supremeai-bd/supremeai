# SupremeAI - API Versioning Strategy
## Production-Ready Versioning Guidelines

---

## Table of Contents

1. [Versioning Philosophy](#versioning-philosophy)
2. [Versioning Scheme](#versioning-scheme)
3. [URL Structure](#url-structure)
4. [Version Lifecycle](#version-lifecycle)
5. [Deprecation Process](#deprecation-process)
6. [Breaking vs Non-Breaking Changes](#breaking-vs-non-breaking-changes)
7. [Implementation Guide](#implementation-guide)
8. [Client Migration Path](#client-migration-path)

---

## Versioning Philosophy

SupremeAI follows **semantic versioning** principles adapted for REST APIs:

- **MAJOR version**: Breaking changes (v1 → v2)
- **MINOR version**: New features, backward compatible (within major version via feature flags)
- **PATCH version**: Bug fixes (transparent to clients)

### Core Principles

1. **Backward Compatibility**: New versions must not break existing clients
2. **Clear Communication**: Deprecation warnings 6+ months before removal
3. **Grace Period**: Support old versions for at least 12 months after deprecation
4. **Documentation**: All versions documented with migration guides

---

## Versioning Scheme

### URL-Based Versioning (Primary Method)

```
Base URL: https://api.supremeai.com/api/v{major_version}/
```

**Examples:**
```bash
# v1 (Current Stable)
GET /api/v1/agents
POST /api/v1/conversations/{id}/messages

# v2 (Future)
GET /api/v2/agents
POST /api/v2/conversations/{id}/messages
```

### Why URL-Based Over Other Methods?

| Method | Pros | Cons | SupremeAI Choice |
|--------|------|------|------------------|
| **URL Path** | Clear, cacheable, proxy-friendly | URL changes | ✅ **PRIMARY** |
| Header | Clean URLs | Harder to debug, caching issues | ❌ |
| Query Param | Simple | Not cacheable, messy | ❌ |
| Content Negotiation | Flexible | Complex implementation | ❌ |

---

## URL Structure

### Complete URL Pattern

```
https://{environment}.supremeapi.com/api/v{version}/{resource}/{identifier}/{sub-resource}
```

### Resource Naming Conventions

| Convention | Rule | Example |
|------------|------|---------|
| **Nouns only** | Use nouns, not verbs | `/agents` not `/getAgents` |
| **Plural** | Collections are plural | `/agents`, `/conversations` |
| **kebab-case** | Multi-word resources | `/hitl-approvals` not `/hitlApprovals` |
| **Lowercase** | Always lowercase | `/api-keys` not `/API_Keys` |

### Endpoint Categories by Domain

#### Authentication & Users (`/auth`, `/users`)
```bash
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
GET    /api/v1/auth/me
PUT    /api/v1/users/{id}
DELETE /api/v1/users/{id}
```

#### Agents (`/agents`)
```bash
GET    /api/v1/agents                    # List agents
POST   /api/v1/agents                    # Create agent
GET    /api/v1/agents/{id}               # Get agent details
PUT    /api/v1/agents/{id}               # Update agent
DELETE /api/v1/agents/{id}               # Delete agent
POST   /api/v1/agents/{id}/activate      # Activate agent
POST   /api/v1/agents/{id}/pause         # Pause agent
GET    /api/v1/agents/{id}/stats         # Agent statistics
GET    /api/v1/agents/{id}/config        # Get configuration
PUT    /api/v1/agents/{id}/config        # Update configuration
```

#### Conversations (`/conversations`)
```bash
GET    /api/v1/conversations             # List conversations
POST   /api/v1/conversations             # Create conversation
GET    /api/v1/conversations/{id}        # Get conversation
DELETE /api/v1/conversations/{id}        # Delete conversation
POST   /api/v1/conversations/{id}/messages     # Send message
GET    /api/v1/conversations/{id}/messages      # Get messages
PUT    /api/v1/conversations/{id}/title         # Update title
POST   /api/v1/conversations/{id}/summarize     # Trigger summary
```

#### Memory Service (`/memory`)
```bash
POST   /api/v1/memory/store              # Store memory
GET    /api/v1/memory/search             # Semantic search
DELETE /api/v1/memory/{id}               # Delete memory
GET    /api/v1/memory/stats              # Memory statistics
POST   /api/v1/memory/import             # Bulk import
GET    /api/v1/memory/export             # Export memories
```

#### HITL Engine (`/hitl`)
```bash
GET    /api/v1/hitl/approvals            # List pending approvals
GET    /api/v1/hitl/approvals/{id}       # Get approval detail
POST   /api/v1/hitl/approvals/{id}/approve    # Approve request
POST   /api/v1/hitl/approvals/{id}/reject     # Reject request
POST   /api/v1/hitl/approvals/{id}/escalate   # Escalate request
GET    /api/v1/hitl/my-approvals         # My pending reviews
GET    /api/v1/hitl/stats                # HITL statistics
```

#### Tool Execution (`/tools`)
```bash
GET    /api/v1/tools                     # Available tools
GET    /api/v1/tools/{name}              # Tool schema
POST   /api/v1/tools/{name}/execute      # Execute tool
GET    /api/v1/tools/executions          # Execution history
GET    /api/v1/tools/executions/{id}     # Execution detail
```

#### Admin Endpoints (`/admin`)
```bash
GET    /api/v1/admin/users               # User management
GET    /api/v1/admin/stats               # Platform statistics
GET    /api/v1/admin/audit-logs          # Audit trail
POST   /api/v1/admin/maintenance         # Maintenance mode
GET    /api/v1/admin/health              # Health check
```

---

## Version Lifecycle

### Version States

```
┌──────────┐    ┌───────────┐    ┌────────────┐    ┌──────────┐
│  ALPHA   │───►│   BETA    │───►│  STABLE    │───►│DEPRECATED│
│ (dev)    │    │ (testing) │    │(production)│    │ (sunset) │
└──────────┘    └───────────┘    └────────────┘    └──────────┘
                      │                                  │
                      ▼                                  ▼
                 ┌──────────┐                    ┌──────────┐
                 │  CANARY  │                    │RETIRED   │
                 │ (limited)│                    │(removed) │
                 └──────────┘                    └──────────┘
```

### Timeline Example: v1 Lifecycle

| Phase | Date | Status | Notes |
|-------|------|--------|-------|
| Alpha | Jan 2024 | Internal testing | Feature development |
| Beta | Mar 2024 | Early adopters | Limited rollout |
| Stable | Jun 2024 | General availability | Full production support |
| Deprecated | Dec 2025 | No new users | Migration required |
| Retired | Jun 2026 | Removed | End of life |

---

## Deprecation Process

### Deprecation Headers

When an endpoint is deprecated, include these headers:

```http
HTTP/1.1 200 OK
Content-Type: application/json
Deprecation: true
Sunset: Sat, 01 Jun 2026 00:00:00 GMT
Link: </api/v2/agents>; rel="successor-version"
```

### Response Body for Deprecated Endpoints

```json
{
  "data": { ... },
  "deprecation_notice": {
    "deprecated": true,
    "deprecated_since": "2025-01-01",
    "sunset_date": "2026-06-01",
    "migration_guide": "https://docs.supremeai.com/migration-v1-to-v2",
    "successor_endpoint": "/api/v2/agents"
  }
}
```

### Deprecation Timeline

| Phase | Duration | Actions |
|-------|----------|---------|
| **Announcement** | Day 0 | Blog post, email, changelog |
| **Warning Period** | 0-6 months | Headers + response warnings |
| **Soft Enforcement** | 6-9 months | Rate limiting on old version |
| **Hard Enforcement** | 9-12 months | Errors pointing to new version |
| **Removal** | 12+ months | Endpoint returns 410 Gone |

---

## Breaking vs Non-Breaking Changes

### Non-Breaking Changes (Same Version)

These changes do NOT require a new major version:

✅ **Adding** new endpoints  
✅ **Adding** optional request parameters  
✅ **Adding** new response fields  
✅ **Adding** new enum values  
✅ **Changing** error messages  
✅ **Fixing** bugs that return correct data  

### Breaking Changes (Require New Major Version)

These changes DO require a new major version:

❌ **Removing** or renaming endpoints  
❌ **Removing** or renaming request/response fields  
❌ **Changing** field types  
❌ **Making** optional fields required  
❌ **Changing** authentication method  
❌ **Changing** error response format  
❌ **Changing** pagination structure  
❌ **Removing** enum values  

---

## Implementation Guide

### FastAPI Router Setup

```python
# app/api/v1/router.py
from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1",
    tags=["v1"],
    deprecated=False,  # Set True when deprecating this version
)

# Import and include sub-routers
from app.api.v1.endpoints import auth, agents, conversations, memory, hitl

router.include_router(auth.router, prefix="/auth", tags=["authentication"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
router.include_router(memory.router, prefix="/memory", tags=["memory"])
router.include_router(hitl.router, prefix="/hitl", tags=["hitl"])

# Version-specific middleware
@router.middleware("http")
async def add_version_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-API-Version"] = "v1"
    response.headers["X-API-Support-Until"] = "2026-06-01"
    return response
```

### Version Detection Middleware

```python
# app/middleware/version.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

SUPPORTED_VERSIONS = {
    "v1": {"status": "stable", "deprecated": False},
    "v2": {"status": "beta", "deprecated": False},
}

class VersionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract version from path
        path_parts = request.url.path.split("/")
        
        # Find version segment (e.g., 'v1', 'v2')
        api_index = None
        for i, part in enumerate(path_parts):
            if part == "api" and i + 1 < len(path_parts):
                api_index = i + 1
                break
        
        if api_index:
            version = path_parts[api_index]
            
            if version not in SUPPORTED_VERSIONS:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "UNSUPPORTED_API_VERSION",
                            "message": f"API version '{version}' is not supported",
                            "supported_versions": list(SUPPORTED_VERSIONS.keys())
                        }
                    }
                )
            
            version_info = SUPPORTED_VERSIONS[version]
            
            if version_info["deprecated"]:
                logger.warning(f"Deprecated API version used: {version}")
                
            # Add version info to request state for downstream use
            request.state.api_version = version
            request.state.version_status = version_info["status"]
        
        response = await call_next(request)
        return response
```

### Versioned Response Models

```python
# app/schemas/v1/agent.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AgentResponseV1(BaseModel):
    """V1 Agent Response Schema"""
    
    id: str
    name: str
    type: str
    status: str
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "uuid-here",
                "name": "Research Assistant",
                "type": "task_agent",
                "status": "active",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }

# V2 might have additional fields
class AgentResponseV2(AgentResponseV1):
    """V2 Agent Response Schema (extends V1)"""
    
    capabilities: list[str] = []
    health_score: Optional[float] = None
    last_execution_summary: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "uuid-here",
                "name": "Research Assistant",
                "type": "task_agent",
                "status": "active",
                "created_at": "2024-01-15T10:30:00Z",
                "capabilities": ["web_search", "code_analysis"],
                "health_score": 0.95,
                "last_execution_summary": {
                    "duration_seconds": 12.5,
                    "tokens_used": 1500,
                    "success": True
                }
            }
        }
```

---

## Client Migration Path

### Migration Checklist for Clients

1. **Update Base URL**: Change from `/api/v1/` to `/api/v2/`
2. **Review Breaking Changes**: Check changelog for removed/changed fields
3. **Update Request Models**: Add newly required fields
4. **Update Response Handling**: Handle new response fields
5. **Test in Staging**: Validate against staging environment
6. **Monitor Deprecation Warnings**: Log and address warnings
7. **Plan Cutover**: Schedule migration before hard enforcement

### Client-Side Version Handling

```typescript
// TypeScript example for handling multiple API versions
interface ApiClientConfig {
  baseUrl: string;
  version: 'v1' | 'v2';
  onDeprecated?: (notice: DeprecationNotice) => void;
}

class SupremeAIClient {
  private config: ApiClientConfig;
  
  constructor(config: ApiClientConfig) {
    this.config = config;
  }
  
  async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.config.baseUrl}/api/${this.config.version}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-API-Version': this.config.version,
        ...options?.headers,
      },
    });
    
    // Check for deprecation notice
    const deprecation = response.headers.get('Deprecation');
    if (deprecation === 'true' && this.config.onDeprecated) {
      const sunset = response.headers.get('Sunset');
      const successor = response.headers.get('Link')?.match(/<([^>]+)>/)?.[1];
      
      this.config.onDeprecated({
        deprecated: true,
        sunsetDate: sunset || '',
        successorEndpoint: successor || '',
      });
    }
    
    // Handle 410 Gone for retired endpoints
    if (response.status === 410) {
      throw new Error('This API version has been retired. Please upgrade.');
    }
    
    return response.json();
  }
}
```

---

## Quick Reference Card

| Aspect | Decision |
|--------|----------|
| **Versioning Method** | URL Path (`/api/v1/`) |
| **Current Version** | v1 (Stable) |
| **Next Version** | v2 (Beta - Planned) |
| **Deprecation Notice** | `Deprecation` header + response field |
| **Sunset Timeline** | 12+ months after deprecation |
| **Backward Compatibility** | Guaranteed within major version |
| **Documentation** | Per-version docs at `docs.supremeai.com/v1/` |
| **Migration Support** | Guides, SDK updates, grace period |

---

*Document Version: 1.0.0*
*Last Updated: 2024*
*Maintained by: SupremeAI Platform Team*
