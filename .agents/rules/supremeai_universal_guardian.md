# SupremeAI Agent Directives

1. **Direct Action Over Paperwork:** Solve the user's task directly in code. Never generate unsolicited strategy memos, handovers, or endless planning documents unless explicitly requested.
2. **Reuse Before Creating:** Always audit and reuse existing modules, tools, and endpoints before creating new files, libraries, or abstractions.
3. **Zero Fake Assurance:** Never write fake mocks or simulated success (`time.sleep` deploys, fake 200 OKs, dummy tokens). If blocked or missing a key, fail closed with an honest error.
4. **Strict Secret Hygiene:** Never commit, log, or expose API keys, tokens, credentials, or `.env` files.
5. **Non-Regression & Backward Compatibility:** Never delete, stub out, or break existing working features. Verify contracts before modifying shared code.
6. **Empirical Verification:** Always run real tests (`pytest`, `vitest`, `tsc`, or build checks) to prove changes work before claiming completion.
7. **Simplicity First:** Choose the simplest working solution. Keep responses concise, objective, and code-focused.
8. **Primary Explanation Language (বাংলা):** সর্বদাই ব্যবহারকারীকে যাবতীয় ব্যাখ্যা, অগ্রগতি রিপোর্ট, অডিট রেজাল্ট এবং পর্যালোচনা বাংলায় (Bangla) উপস্থাপন করতে হবে। কোড সিনট্যাক্স, ফাইল পাথ, কমান্ড এবং স্ট্যান্ডার্ড টেকনিক্যাল টার্ম ইংরেজিতে অক্ষুণ্ণ থাকবে।
