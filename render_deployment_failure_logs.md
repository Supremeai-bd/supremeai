# Render Deployment Failure Logs (র ডিপ্লয়মেন্ট ফেইলিয়র লগ রিপোর্ট)

**তারিখ ও সময়:** 2026-08-13
**ইমপ্যাক্টেড সার্ভিসসমূহ:**
1. `User Backend` (`srv-d9d3n58js32c738n79k0`)
2. `Admin Backend` (`srv-d9fg48bh523c73f63bb0`)

---

## ১. User Backend (`srv-d9d3n58js32c738n79k0`) Raw Failure Log

```json
{
  "deploy": {
    "id": "dep-d9v4683jgndc73akev90",
    "image": {
      "ref": "ghcr.io/saifulhaqueniloy/supremeai-backend:latest",
      "sha": "sha256:5c63b3fac67983e9f2b9959345de68a1e804a029d45c36f8b363ce6bb56ece6b"
    },
    "status": "update_failed",
    "trigger": "api",
    "createdAt": "2026-08-13T22:20:16.172189Z",
    "finishedAt": "2026-08-13T22:22:43.957365Z"
  },
  "event": {
    "details": {
      "deployId": "dep-d9v4683jgndc73akev90",
      "deployStatus": "failed",
      "reason": {
        "failure": {
          "evicted": false,
          "nonZeroExit": 3
        }
      },
      "status": 4
    },
    "id": "evt-d9v47cvjj10s73efqr7g",
    "timestamp": "2026-08-13T22:22:43.988722Z",
    "type": "deploy_ended"
  }
}
```

---

## ২. Admin Backend (`srv-d9fg48bh523c73f63bb0`) Raw Failure Log

```json
{
  "deploy": {
    "id": "dep-d9v468egekts739bcdf0",
    "image": {
      "ref": "ghcr.io/saifulhaqueniloy/supremeai-backend:latest",
      "sha": "sha256:5c63b3fac67983e9f2b9959345de68a1e804a029d45c36f8b363ce6bb56ece6b"
    },
    "status": "update_failed",
    "trigger": "api",
    "createdAt": "2026-08-13T22:20:17.474566Z",
    "finishedAt": "2026-08-13T22:22:36.194563Z"
  },
  "event": {
    "details": {
      "deployId": "dep-d9v468egekts739bcdf0",
      "deployStatus": "failed",
      "reason": {
        "failure": {
          "evicted": false,
          "nonZeroExit": 3
        }
      },
      "status": 4
    },
    "id": "evt-d9v47b4jio4c73b4jgj0",
    "timestamp": "2026-08-13T22:22:36.225625Z",
    "type": "deploy_ended"
  }
}
```

---

## ৩. একক ও সুনির্দিষ্ট মূল কারণ (Single Definite Root Cause)

Render সার্ভিস দুটি `runtime: image` মোডে ক্লাউড থেকে ইমেজ পুল করে (`ghcr.io/saifulhaqueniloy/supremeai-backend:latest`)। লোকাল পিসিতে ডকার ইমেজ সফলভাবে বিল্ড হলেও তা এখনও GitHub Container Registry (GHCR)-এ পুশ (`docker push`) করা হয়নি। ফলে Render আগের পুরোনো অপরিবর্তিত/ফেইলিং ইমেজটি পুল করে রান করার চেষ্টা করায় ৩ বার হেলথ-চেক ব্যর্থ হয়ে ডিপ্লয়মেন্ট ফেইল (`nonZeroExit: 3`) হয়েছে।
