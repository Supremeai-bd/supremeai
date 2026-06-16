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

