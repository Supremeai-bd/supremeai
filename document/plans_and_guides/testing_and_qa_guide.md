# 🧪 Testing & Quality Assurance Guide

সুপ্রিম এআই ২.০ (SupremeAI 2.0) প্রজেক্টের স্ট্যাবিলিটি ও কোড কোয়ালিটি নিশ্চিত করার জন্য টেস্টিং ফ্রেমওয়ার্ক এবং অটোমেটেড কিউএ গাইডলাইন নিচে দেওয়া হলো:

## ১. টেস্ট এনভায়রনমেন্ট এবং টুলস (Test Suite & Tools)

প্রজেক্টে টেস্টিংয়ের জন্য `pytest` লাইব্রেরি ব্যবহার করা হয়েছে।
* **টেস্ট লোকেশন**: `/tests` ফোল্ডারে সমস্ত পাইথন টেস্ট স্ক্রিপ্ট রয়েছে।
* **টেস্ট সংখ্যা**: বর্তমানে কোডবেজে **৪৮টি টেস্ট কেস** সচল রয়েছে।

---

## ২. কীভাবে টেস্ট রান করবেন (Running Tests)

প্রজেক্ট রুট ডিরেক্টরি থেকে নিচের কমান্ডগুলো ব্যবহার করে পরীক্ষা সম্পন্ন করুন:

### ক. সবগুলো টেস্ট রান করতে:
```powershell
pytest
```

### খ. কোনো নির্দিষ্ট ফাইল রান করতে (যেমন- `test_core.py`):
```powershell
pytest tests/test_core.py
```

### গ. টেস্ট কাভারেজ (Code Coverage) রিপোর্ট দেখতে:
```powershell
pytest --cov=.
```

---

## ৩. প্রধান টেস্ট ফাইলসমূহের বিবরণ (Key Test Modules)

* **`tests/test_core.py`**:
  * `IntentClassifier` এর ক্লাসিফিকেশন লজিক পরীক্ষা করে।
  * `ModelRouter` এর এপিআই ফেইলওভার এবং ওলামা/লোকাল ফলব্যাক চেইন ভেরিফাই করে।
  * SQLite ভিত্তিক `AdminGodLayer` এর পারমিশন সেট/গেট ও রাউন্ডট্রিপ চেক করে।
* **`tests/test_advanced.py`**:
  * `TaskRouter` এর কাজের প্যাটার্ন বিশ্লেষণ ও রাউটিং লজিক যাচাই করে।
* **`tests/test_crew_mcp.py`**:
  * মাল্টি-এজেন্ট ইন্টারঅ্যাকশন ও MCP সার্ভারের ইন্টিগ্রেশন মক ভ্যালু দিয়ে টেস্ট করে।
* **`tests/test_monitoring.py`**:
  - `DockerSandbox` এর নিরাপত্তা পলিসি ও লোকাল ফলব্যাক মোড ভেরিফাই করে।
  - `CostAuditor` এর SQLite থেকে খরচ হিসাব এবং রিপোর্ট তৈরি নিশ্চিত করে।
  - `PlanSorter` এর প্ল্যান অর্গানাইজার এবং `HealthChecker` এর নিয়মিত ডিপেন্ডেন্সি চেকিং ভেরিফাই করে।
  - `AuditLogger` এর মাধ্যমে এআই এর স্বয়ংক্রিয় রোটেশন সিদ্ধান্ত ও ওটিপি পোলিং এর অডিট লগ ট্রেইল নিশ্চিত করে।
  * ইনপুট স্যানিটাইজার, রিয়েল-টাইম জেনারেশন মনিটর, ফ্যাকচুয়াল ভেরিফায়ার (SymPy সহ), কোড ভ্যালিডেটর (AST syntax, indentation, module import exist-check, undefined variables), আউটপুট ভ্যালিডেটর (multi-model consensus, enhanced confidence scorer, human review policy), এবং এরর প্যাটার্ন ডাটাবেস (AI mistake logs) পরীক্ষা করে।

---
*Last Synced with Missing Skills, Dependencies & Tools Analysis: 2026-06-17*

