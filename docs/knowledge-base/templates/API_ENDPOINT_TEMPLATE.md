# {Endpoint Name}

**Location**: `{file_path}`  
**Method**: `{HTTP_METHOD}`  
**Path**: `{path}`  
**Authentication**: {Required/Optional/None}  
**Permissions**: {permission_list}

---

## 📋 Overview

{Brief description of what this endpoint does}

**Purpose**: {Why this endpoint exists}

**Use Cases**:
- {Use case 1}
- {Use case 2}
- {Use case 3}

---

## 🔐 Authentication

{Authentication requirements}

**Required Headers**:
```
Authorization: Bearer {token}
```

**OR**

```
X-API-Key: {api_key}
```

---

## 📥 Request

### Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| `Authorization` | string | Yes | Bearer token or API key |
| `Content-Type` | string | Yes | `application/json` |

### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `{param_name}` | {type} | {Yes/No} | {description} |

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `{param_name}` | {type} | {Yes/No} | {default} | {description} |

### Request Body

```json
{
  "{field_name}": {type} - {description}
}
```

**Field Descriptions**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `field_name` | string | Yes | Max 255 chars | {description} |
| `field_name` | number | No | Min 0, Max 100 | {description} |
| `field_name` | boolean | No | Default: false | {description} |

---

## 📤 Response

### Success Response (200 OK)

```json
{
  "id": "uuid",
  "field_name": "value",
  "created_at": "2025-01-04T00:00:00Z"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `field_name` | {type} | {description} |

### Error Responses

#### 400 Bad Request

```json
{
  "detail": "Validation error",
  "code": "VALIDATION_ERROR",
  "fields": {
    "email": "Invalid email format"
  }
}
```

**Common Causes**:
- Missing required fields
- Invalid field values
- Malformed JSON

#### 401 Unauthorized

```json
{
  "detail": "Invalid or expired token",
  "code": "UNAUTHORIZED"
}
```

**Common Causes**:
- Missing authentication header
- Expired token
- Invalid API key

#### 403 Forbidden

```json
{
  "detail": "Permission denied",
  "code": "FORBIDDEN"
}
```

**Common Causes**:
- Insufficient permissions
- Resource ownership mismatch

#### 404 Not Found

```json
{
  "detail": "Resource not found",
  "code": "NOT_FOUND"
}
```

**Common Causes**:
- Invalid ID
- Resource deleted
- Wrong endpoint

#### 429 Too Many Requests

```json
{
  "detail": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

**Common Causes**:
- Too many requests
- IP rate limiting

#### 500 Internal Server Error

```json
{
  "detail": "Internal server error",
  "code": "INTERNAL_ERROR",
  "request_id": "uuid"
}
```

**Common Causes**:
- Database error
- External service failure
- Unexpected error

---

## 💡 Examples

### cURL

```bash
curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field_name": "value"
  }'
```

### Python

```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "field_name": "value"
        }
    )
    
    data = response.json()
    print(data)
```

### JavaScript

```javascript
const response = await fetch(
  'https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint}',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      field_name: 'value'
    })
  }
);

const data = await response.json();
console.log(data);
```

### TypeScript

```typescript
interface RequestBody {
  field_name: string;
}

const response = await fetch(
  'https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint}',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      field_name: 'value'
    } as RequestBody)
  }
);

const data = await response.json() as ResponseType;
console.log(data);
```

---

## ✅ Verification Steps

**How to verify this endpoint works**:

1. **Get Authentication Token**:
   ```bash
   TOKEN=$(curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"user@example.com","password":"password"}' | jq -r '.access_token')
   ```

2. **Test Endpoint**:
   ```bash
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint} \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"field_name":"value"}'
   ```

3. **Verify Response**:
   ```bash
   # Should return 200 OK
   # Should return valid JSON
   # Should contain expected fields
   ```

4. **Test Error Cases**:
   ```bash
   # Without auth (should return 401)
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint}
   
   # With invalid data (should return 400)
   curl -X POST https://supremeai-backend-08zd.onrender.com/api/v1/{endpoint} \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"invalid_field": "value"}'
   ```

---

## 🔗 Related Documentation

- [Authentication Documentation](../12-AUTHENTICATION_DOCUMENTATION.md)
- [Authorization Documentation](../13-AUTHORIZATION_DOCUMENTATION.md)
- [API Overview](../11-API_DOCUMENTATION.md)
- [Related Endpoint](./related-endpoint.md)

---

## 📊 Rate Limiting

**Limits**:
- {rate_limit} requests per minute
- {rate_limit} requests per hour
- {rate_limit} requests per day

**Headers**:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1640003600
```

---

## 🚨 Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Missing or invalid token | Check authentication header |
| 403 Forbidden | Insufficient permissions | Check user permissions |
| 404 Not Found | Invalid ID or endpoint | Verify endpoint and ID |
| 429 Rate Limited | Too many requests | Wait and retry |
| 500 Server Error | Internal error | Contact support |

---

## 📝 Notes

- {Important note 1}
- {Important note 2}
- {Limitation or constraint}

---

**Document Status**: ✅ Complete and Verified  
**Last Updated**: 2025-01-04  
**Owner**: API Team  
**Classification**: Internal