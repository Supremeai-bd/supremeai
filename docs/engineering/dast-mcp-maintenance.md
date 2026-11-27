# DAST স্থগিত ও MCP Tower failure handling

- ব্যবহারকারীর নির্দেশে nightly `dast` job-এ `if: false` দেওয়া হয়েছে। Schedule, manual dispatch ও `run_all`—কোনোটিতেই ZAP চলবে না। এটি **স্ক্যান পাস নয়**; ZAP কভারেজ অনুপস্থিত। আলাদা free-tier staging নেই বলে production-এ scan চালানো হয়নি।
- ভবিষ্যতে পুনরায় চালু করার আগে অনুমোদিত staging target, পরিবেশ ও scan-এর প্রভাব মানব পর্যালোচনায় নিশ্চিত করতে হবে। বিদ্যমান target validation কেবল URL syntax যাচাই করে; এটি staging বনাম production শনাক্ত করে না। Production URL কখনো staging হিসেবে কনফিগার করবেন না।
- Core MCP Tower proxy-তে initialized notification-এর HTTP/transport failure আর উপেক্ষা হয় না; MCP JSON-RPC error ও `isError` tool response 502। পরীক্ষাগুলো mocked।
- একক Render restart কেবল known service ও প্রয়োজনীয় credentials থাকলে পাঠানো হয়। ব্যর্থ বা অনিশ্চিত upstream mutation-এ success নয়; timeout হলে retry-এর আগে মানব reconciliation প্রয়োজন। Restart accepted হওয়ার পর telemetry অনুপস্থিত থাকলেও response সেই ঝুঁকি জানায়। `reboot-all` আগে শুধু status দেখিয়ে reboot-এর আভাস দিত; এখন তা 501 (বাস্তব bulk reboot implementation নেই)।
- Local route introspection-এ monolith Core-এ এই proxy routes mounted দেখা গেছে। Tests isolated router-এ, mocked HTTP transport দিয়ে; live Tower/Render restart, staging ZAP বা production security/load test চালানো হয়নি। Mutation-এর distributed idempotency ও বাস্তব deployment protocol যাচাই এখানে করা হয়নি।
