# 🔌 API Endpoints Specification

সুপ্রিম এআই ২.০ (SupremeAI 2.0) এপিআই গেটওয়ের সমস্ত এন্ডপয়েন্ট, রিকোয়েস্ট স্কিমা এবং রেসপন্স ফরম্যাটের বিস্তারিত বিবরণ নিচে দেওয়া হলো:

## ১. টাস্ক এক্সিকিউশন এন্ডপয়েন্ট (Task Execution API)

ইউজারের প্রম্পট বা কোনো কমান্ড রান করার জন্য এই এন্ডপয়েন্টটি ব্যবহৃত হয়। এটি স্বয়ংক্রিয়ভাবে ইন্টেন্ট ও বাজেট অনুযায়ী সেরা মডেল চয়ন করে কাজ সম্পন্ন করে।

* **URL Path**: `/api/v1/task/execute`
* **Method**: `POST`
* **Content-Type**: `application/json`

*নোট: এই এন্ডপয়েন্টের প্রতিটি রিকোয়েস্ট ও রেসপন্স সরাসরি Multi-Layer Hallucination Defense (v2.1) এবং AST ভ্যালিডেশন লেয়ার দ্বারা ফিল্টার করা হয়।*


### 📥 Request Body Schema (JSON)
```json
{
  "task": "write a python function to sort a list",
  "task_type": "coding",
  "max_cost": 0.05,
  "admin_token": "optional_token_string"
}
```

| Field Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `task` | String | Yes | - | যে কাজটি এআই সম্পন্ন করবে (প্রম্পট বা কমান্ড)। |
| `task_type` | String | No | `"general"` | কাজের ধরণ (`general`, `coding`, `admin`, `translation`)। |
| `max_cost` | Float | No | `0.01` | কাজের জন্য নির্ধারিত সর্বোচ্চ খরচ (USD)। |
| `admin_token` | String | No | `null` | অ্যাডমিন প্রিভিলেজড অ্যাকশন রান করার টোকেন। |

### 📤 Success Response (200 OK)
```json
{
  "success": true,
  "result": "def sort_list(lst):\n    return sorted(lst)",
  "provider": "openrouter/meta-llama/llama-3-8b-instruct",
  "cost": 0.00015,
  "error": null
}
```

### 📤 Error Response (403 Forbidden - Admin Restricted)
```json
{
  "detail": "Action not allowed by Admin God Layer rules"
}
```

---

## ২. সিস্টেম হেলথ চেক এন্ডপয়েন্ট (System Health Check)

সার্ভার সচল আছে কিনা এবং রানটাইম স্ট্যাটাস চেক করার এপিআই।

* **URL Path**: `/api/v1/health`
* **Method**: `GET`

### 📤 Success Response (200 OK)
```json
{
  "status": "ok",
  "version": "2.0.0",
  "description": "SupremeAI Master Agent API"
}
```

---

## ৩. রিয়েল-টাইম কোড কমপ্লিশন এন্ডপয়েন্ট (Real-time Code Completion API)

ভিএস কোড এক্সটেনশনের মাধ্যমে রিয়েল-টাইম কোড কমপ্লিশন প্রদানের জন্য এই এন্ডপয়েন্টটি ব্যবহৃত হয়। এটি কম-ল্যাটেন্সি মডেল ব্যবহার করে দ্রুত সাজেশন প্রদান করে।

* **URL Path**: `/api/chat/completion`
* **Method**: `POST`
* **Content-Type**: `application/json`

### 📥 Request Body Schema (JSON)
```json
{
  "prefix": "def sort_list(lst):\n    ret",
  "suffix": "urn sorted(lst)",
  "filePath": "/path/to/file.py",
  "language": "python"
}
```

### 📤 Success Response (200 OK)
```json
{
  "success": true,
  "suggestions": ["urn sorted(lst)"]
}
```

---

## ৪. ক্লাউড ফাংশন ওসিআর এন্ডপয়েন্ট (Cloud Function OCR API)

মাল্টি-ল্যাঙ্গুয়েজ এবং বাংলা ইমেজ থেকে টেক্সট এবং টেবিল এক্সট্র্যাকশন করার জন্য এই এন্ডপয়েন্টগুলো ব্যবহৃত হয়।

### এপিআই ১: মাল্টি-ল্যাঙ্গুয়েজ ওসিআর (Multi-language OCR)
* **URL Path / Endpoint**: `https://region-supremeai.cloudfunctions.net/processOCR`
* **Method**: `POST`
* **Headers**: `Authorization: Bearer <token>`
* **Request Body**:
```json
{
  "imageUrls": ["https://example.com/image.jpg"],
  "projectId": "project_123",
  "userId": "user_456",
  "languages": ["en", "bn"]
}
```
* **Success Response**:
```json
{
  "success": true,
  "results": [
    {
      "imageUrl": "https://example.com/image.jpg",
      "success": true,
      "textLength": 120,
      "linesCount": 5,
      "tableDetected": false
    }
  ],
  "summary": {
    "total": 1,
    "successful": 1,
    "failed": 0
  },
  "_meta": {
    "timestamp": "2026-06-16T17:00:00Z",
    "version": "2.1.0-international"
  }
}
```

### এপিআই ২: বাংলা ওসিআর (Bengali OCR)
* **URL Path / Endpoint**: `https://region-supremeai.cloudfunctions.net/processBengaliOCR` (প্রসেস ও প্যারামিটার একই, ব্যাকওয়ার্ড কমপ্যাটিবিলিটির জন্য সংরক্ষিত)

## ৫. রেন্ডার অ্যাকচুয়েটর হেলথ চেক (Render Actuator Health Check)
রেন্ডার ডিপ্লয়মেন্ট এবং হেলথ চেক ভ্যালিডেশনের জন্য ব্যাকওয়ার্ড কমপ্যাটিবল এন্ডপয়েন্ট।

* **URL Path**: `/actuator/health`
* **Method**: `GET`

### 📤 Success Response (200 OK)
```json
{
  "status": "UP",
  "orchestrator": "online"
}
```

---

## ৬. ক্লাউড ডিস্ট্রিবিউশন ড্যাশবোর্ড এপিআই (Cloud Distribution Dashboard API)
মাল্টি-ক্লাউড ট্রাফিক ডিস্ট্রিবিউশন, প্রতিটি ক্লাউড নোডের অবস্থা এবং রিয়েল-টাইম স্ট্যাটিসটিক্স দেখার এন্ডপয়েন্ট।

* **URL Path**: `/admin/cloud-distribution`
* **Method**: `GET`

### 📤 Success Response (200 OK)
```json
{
  "distribution": {
    "gcp_cloud_run": {
      "status": "active",
      "current_requests": 150,
      "capacity_remaining": 1999850,
      "utilization_pct": 0.0075,
      "latency_ms": 48.5,
      "region": "us-central1"
    },
    "railway": {
      "status": "active",
      "current_requests": 120,
      "capacity_remaining": 499880,
      "utilization_pct": 0.024,
      "latency_ms": 75.2,
      "region": "us-east"
    },
    "render": {
      "status": "active",
      "current_requests": 85,
      "capacity_remaining": 665,
      "utilization_pct": 11.3,
      "latency_ms": 115.8,
      "region": "oregon"
    }
  },
  "total_requests": 355,
  "active_providers": 3,
  "strategy": "parallel_active_active",
  "rebalance_interval": "1 hour"
}
```


## ৭. GCP Free Tier Health & Queue Endpoints
মাল্টি-ক্লাউড GCP node, Firestore verification queue এবং Pub/Sub task queue-এর status দেখার এন্ডপয়েন্টগুলো।

* **URL Path**: `/gcp/health`
* **Method**: `GET`
* **Success Response**:
```json
{
  "status": "ok",
  "cloud_run": {"success": true, "provider": "gcp_cloud_run"},
  "firestore_mode": "local_sqlite",
  "pubsub_mode": "local_sqlite",
  "cloud_functions": {"configured": false}
}
```

* **URL Path**: `/gcp/verification-queue/stats`
* **Method**: `GET`
* **Success Response**:
```json
{
  "provider": "local_sqlite",
  "pending": 0,
  "verified": 1,
  "total": 1
}
```

* **URL Path**: `/gcp/pubsub/stats`
* **Method**: `GET`
* **Success Response**:
```json
{
  "provider": "local_sqlite",
  "topic": "supremeai-tasks",
  "pending": 0,
  "acked": 1,
  "total": 1
}
```
---
*Last Synced with supremeai_1.0 Reusable Options Analysis: 2026-06-20 (Firebase Deployed)*



<!-- Synced with Rule Update: 2026-06-20 (Bangla Pro Tips Rule added) -->

<!-- Synced with Project Status Update: 2026-06-20 (React Studio Client Modularized) -->

<!-- Synced with Backend Optimization Update: 2026-06-20 (Backend production-ready optimized) -->

<!-- Synced with CI/CD Fix: 2026-06-20 (Pytest PYTHONPATH issue resolved in workflow) -->
