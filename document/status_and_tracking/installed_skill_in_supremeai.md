# 🛠️ Installed Skills & Tools in SupremeAI 2.0

SupremeAI ২.০ প্রজেক্টে বিদ্যমান টুলস এবং ডাইনামিক স্কিলগুলোর তালিকা নিচে দেওয়া হলো:

## 🧰 Core Tools (উৎস: `supremeai_2.0/tools/`)
* **multi_account_rotator.py**: একাধিক এআই অ্যাকাউন্ট এবং API Key রোটেশন ও ফেইলওভার ম্যানেজমেন্ট।
* **auto_test_generator.py**: স্বয়ংক্রিয় টেস্ট ফাইল জেনারেটর।
* **bangla_ai_connector.py**: বাংলা ভাষা কানেক্টিভিটি ও প্রম্পট প্রসেসর।
* **bengali_ocr_converter.py**: বাংলা ইমেজ ও ডকুমেন্ট OCR রিডার।
* **coverage_auditor.py**: টেস্ট কাভারেজ অডিটিং টুল।
* **git_knowledge_extractor.py**: গিট রিপোজিটরির কমিট ও কোড নলেজ এক্সট্র্যাক্টর।
* **local_ocr_extractor.py**: লোকাল OCR ইঞ্জিন।
* **local_search_rag.py**: লোকাল ChromaDB এবং সার্চ এপিআই ভিত্তিক RAG ইঞ্জিন।
* **cot_reasoner.py**: চেইন-অফ-থট (CoT) রিজনিং প্রসেসর।
* **browser_agent.py**: ব্রাউজার ব্যবহারের জন্য অটোমেশন স্ক্রিপ্ট।
* **computer_agent.py**: ওএস লেভেলের অটোমেশন প্রসেসর।
* **sync-features.js**: নোডজেএস এবং জাভাস্ক্রিপ্ট স্ক্রিপ্ট সিঙ্ক লজিক।
* **input_sanitizer.py**: প্রম্পট স্যানিটাইজেশন, অস্পষ্টতা ফিল্টার ও PII স্যানিটাইজেশন (Layer 1)।
* **generation_monitor.py**: রিয়েল-টাইম জেনারেশন ট্র্যাকার ও সোর্স অ্যাট্রিবিউশন (Layer 2)।
* **factual_verifier.py**: ওয়েব সার্চ ও গাণিতিক সমীকরণ যাচাইকারক (Layer 3) - ChromaDB লোকাল RAG এর অগ্রাধিকার সহ।
* **code_validator.py**: সিনট্যাক্স, পাথ, ইউআরএল ভ্যালিডেটর (Layer 4) এবং AICodeValidator (v2.1)।
* **output_validator.py**: মাল্টি-মডেল কনসেনসাস, কনফিডেন্স স্কোরিং (Layer 5) এবং HumanReviewPolicy ও EnhancedConfidenceScorer (v2.1)।
* **error_pattern_db.py**: SQLite ভিত্তিক ভুলভ্রান্তি ট্র্যাকিং ডাটাবেস (Meta-Layer) এবং AI mistake logging (v2.1)।
* **docker_sandbox.py**: স্যান্ডবক্সড ডকার কমান্ড এক্সিকিউশন ও লোকাল ফলব্যাক মোড।
* **cost_auditor.py**: SQLite থেকে খরচ ও API ব্যবহার হিসেব করে গ্রাফিকাল কস্ট অডিট রিপোর্ট জেনারেটর।
* **plan_sorter.py**: ইনবক্সের প্ল্যান ফাইলগুলোকে 'Urgent', 'Feature', ও 'Bug' অগ্রাধিকার অনুযায়ী সর্ট করার মেকানিজম।
* **health_checker.py**: দৈনিক সিস্টেমের ডিপেন্ডেন্সি ও এপিআই কি স্ট্যাটাস যাচাইকরণ টুল।
* **audit_logger.py** (উৎস: `core/`): স্বয়ংক্রিয় এআই সিদ্ধান্ত ও ওটিপি ভেরিফিকেশন পোলিং এর tamper-proof অডিট লগ ট্রেইল।



## ⚡ Dynamic Skills (উৎস: `supremeai_2.0/skills/dynamic/`)
* **csv_exporter.py**: এক্সেল ও সিএসভি ফাইল জেনারেটর এবং এক্সপোর্টার।
* **text_summarizer.py**: ডাইনামিক টেক্সট সামারাইজেশন টুল।
* **web_scraper.py**: ডাইনামিক এইচটিএমএল কন্টেন্ট এক্সট্র্যাক্টর।
