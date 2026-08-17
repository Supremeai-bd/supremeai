# SupremeAI 2.0 — Production Environment Endpoint Mapping Specification
_Status: ACTIVE_  
_Last Updated: 2026-08-06_  
_Language: Bangla (বাংলা)_

---

## 📌 সারসংক্ষেপ (Overview)

প্রোডাকশন এনভায়রনমেন্টে সিস্টেমের সিকিউরিটি ও আইসোলেশন নিশ্চিত করতে সমস্ত সাইলেন্ট localhost ফলব্যাক অপসারণ করা হয়েছে। কোন এনভায়রনমেন্টে localhost পরিবর্তনের পর কোন রিয়েল ক্লাউড/প্রোডাকশন URL এবং এনভায়রনমেন্ট ভেরিয়েবল ব্যবহৃত হচ্ছে, তার সম্পূর্ণ একক উৎস (Single Source of Truth) নিচে প্রদান করা হলো।

---

## 🌐 ১. ব্যাকএন্ড এপিআই সার্ভিসেস (Backend API Services)

| সার্ভিস / মডিউল (Module) | এনভায়রনমেন্ট ভেরিয়েবল (Env Var) | পুরাতন ফলব্যাক (Old Localhost) | নতুন প্রোডাকশন URL (Live Target) | এনভায়রনমেন্ট (Scope) |
|---|---|---|---|---|
| **User FastAPI Backend** | SUPREMEAI_USER_BACKEND_URL / VITE_PRIMARY_BACKEND | http://localhost:8000 | https://supremeai-backend.onrender.com | Production / User Portal |
| **Admin FastAPI Backend** | SUPREMEAI_ADMIN_BACKEND_URL / VITE_SECONDARY_BACKEND | http://localhost:8000 | https://supremeai-admin.onrender.com | Production / Admin Portal |
| **User Studio Web Client** | VITE_API_BASE / VITE_API_URL | http://localhost:3000 / 5173 | https://supremeai-lac.vercel.app (Vercel) | Production Web UI |
| **Admin Web Portal** | SUPREMEAI_ADMIN_API_URL | http://localhost:8000 | https://supremeai-admin.web.app (Firebase) | Production Admin UI |

---

## 📱 ২. মোবাইল অ্যাপ্লিকেশান (Flutter Mobile App)

| উপাদান (Component) | এনভায়রনমেন্ট ভেরিয়েবল (Env Var) | পুরাতন ফলব্যাক (Old Localhost) | নতুন প্রোডাকশন URL (Live Target) | কাজের বিবরণ (Behavior) |
|---|---|---|---|---|
| **Flutter Mobile WebSockets** | API_BASE_URL | ws://localhost:8000/api/ws/chat?token=... | wss://supremeai-backend.onrender.com/api/ws/chat | main.dart ফাইল থেকে হার্ডকোড তুলে দিয়ে queryParameters: {'token': ...} পাস করা হচ্ছে। |
| **Mobile Auth & REST API** | API_BASE_URL | http://localhost:8000 | https://supremeai-backend.onrender.com | বিল্ড টাইমে সংজ্ঞায়িত না থাকলে রানটাইমে ফেল-ফাস্ট করবে। |

---

## 💳 ৩. পেমেন্ট ও অথেন্টিকেশন রিডাইরেক্টস (Payment & OAuth Redirects)

| সার্ভিস (Service) | এনভায়রনমেন্ট ভেরিয়েবল (Env Var) | পুরাতন ফলব্যাক (Old Localhost) | নতুন প্রোডাকশন URL (Live Target) | কাজের বিবরণ (Behavior) |
|---|---|---|---|---|
| **Stripe Checkout Base** | CHECKOUT_BASE_URL | http://localhost:3000 | https://supremeai-lac.vercel.app | পেমেন্ট শেষে ইউজারকে প্রোডাকশন স্টুডিওতে রিডাইরেক্ট করে। |
| **GitHub / SSO OAuth** | FRONTEND_BASE_URL | http://localhost:5173 | https://supremeai-lac.vercel.app | integrations.py ও OAuth রিডাইরেক্টের জন্য ব্যবহৃত হয়। |

---

## 🗄️ ৪. ক্লাউড ডাটাবেস ও মেমোরি ক্যাশ (Database & Infrastructure)

| সার্ভিস (Service) | এনভায়রনমেন্ট ভেরিয়েবল (Env Var) | পুরাতন ফলব্যাক (Old Localhost) | নতুন প্রোডাকশন URL (Live Target) | হোস্ট প্রোভাইডার (Provider) |
|---|---|---|---|---|
| **Supabase PostgreSQL** | SUPABASE_DATABASE_URL | postgresql://localhost:5432 | postgresql://postgres...aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres | Supabase AWS Pooler |
| **Upstash Redis Cache** | REDIS_URL | 
edis://localhost:6379 | 
ediss://default:...giving-shepherd-129979.upstash.io:6379 | Upstash Encrypted Redis |
| **Vector DB (Qdrant)** | QDRANT_URL | http://localhost:6333 | https://...qdrant.tech (Infisical Managed) | Qdrant Cloud |
| **Graph DB (Neo4j)** | NEO4J_URI | olt://localhost:7687 | olt+s://...neo4j.io (Infisical Managed) | Neo4j AuraDB |

---

## 🛡️ ৫. সিকিউরিটি ফিল্টার ও ফেল-ফাস্ট নিয়ম (Fail-Fast Rules)

১. **CORS Validation (ackend/core/config.py):**  
   প্রোডাকশনে (ENV=production) যেকোনো localhost বা 127.0.0.1 অরিজিন থাকলে স্বয়ংক্রিয়ভাবে স্ট্রিপ/ফিল্টার করা হয়।

২. **Ollama / Local AI Models (smart_router.py):**  
   প্রোডাকশনে সাইলেন্ট localhost:11434 ফলব্যাক বন্ধ করা হয়েছে। শুধুমাত্র ENV=local হলে ডেভেলপারের পিসিতে লোকাল ফলব্যাক একটিভ হয়।

---

_Generated and Enforced for SupremeAI 2.0 Environment Topology_
