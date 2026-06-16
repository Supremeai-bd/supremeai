"""
AI/ML, LLMs, Prompt Engineering, RAG, and Data Structures & Algorithms
~30 learnings + ~8 patterns = ~38 documents
"""
from seed_data.helpers import _learning, _pattern

AI_ML_LEARNINGS = {

    # ── LLM & Prompt Engineering ───────────────────────────────────────────
    "ai_prompt_engineering": _learning(
        "PATTERN", "AI_ML",
        "Prompt engineering: Be specific and structured. Use system/user/assistant roles. "
        "Chain-of-thought (CoT) for reasoning tasks. Few-shot examples for format consistency. "
        "Temperature 0 for deterministic, 0.7-1.0 for creative. Max tokens to control cost.",
        ["System prompt: Define role, constraints, output format",
         "Few-shot: Provide 2-3 examples of desired input→output",
         "CoT: 'Think step by step before answering'",
         "Temperature 0 for code generation, 0.7 for creative writing"],
        "CRITICAL", 0.97, times_applied=120,
        context={"applies_to": ["ALL"], "providers": ["OpenAI", "Anthropic", "Google"]}
    ),
    "ai_rag_pattern": _learning(
        "PATTERN", "AI_ML",
        "Retrieval-Augmented Generation (RAG): Embed documents into vector DB (Pinecone, Weaviate, "
        "ChromaDB). On query, retrieve top-K similar chunks, inject into prompt as context. "
        "Chunk size 500-1000 tokens with 100-token overlap. Re-rank results before injection.",
        ["Embed: Split docs → embed with ada-002 or all-MiniLM → store in vector DB",
         "Retrieve: Query → embed → cosine similarity → top 5-10 chunks",
         "Augment: System prompt + retrieved context + user query → LLM",
         "Re-rank: Use cross-encoder to re-rank before injection for better relevance"],
        "HIGH", 0.96, times_applied=60,
        context={"applies_to": ["Python", "TypeScript"]}
    ),
    "ai_llm_api_integration": _learning(
        "PATTERN", "AI_ML",
        "LLM API integration: Use streaming for long responses. Implement retry with exponential backoff. "
        "Set timeout (30-60s). Handle rate limits (429). Cache identical prompts. "
        "Log token usage for cost tracking. Use structured output (JSON mode) when available.",
        ["Streaming: OpenAI stream=True, Anthropic stream=True for real-time UX",
         "Retry: 429 → wait retry-after header, 500 → exponential backoff 1s,2s,4s",
         "Cache: Hash(system_prompt + user_prompt) → cache response for identical queries",
         "Cost: Track prompt_tokens + completion_tokens per request, aggregate daily"],
        "HIGH", 0.96, times_applied=80,
        context={"applies_to": ["Python", "Java", "TypeScript"]}
    ),
    "ai_function_calling": _learning(
        "PATTERN", "AI_ML",
        "LLM function/tool calling: Define functions with JSON Schema. LLM decides when to call. "
        "Parse tool_calls from response, execute locally, return results to LLM. "
        "Validate function arguments before execution. Limit available tools to reduce hallucination.",
        ["Define: { 'name': 'get_weather', 'parameters': { 'type': 'object', 'properties': { 'city': { 'type': 'string' } } } }",
         "Parse: response.tool_calls → extract name + args → execute function",
         "Return: Send function result back as tool message → LLM generates final answer",
         "Safety: Validate all args, whitelist allowed functions, never execute arbitrary code"],
        "HIGH", 0.95, times_applied=50,
        context={"applies_to": ["Python", "TypeScript"]}
    ),
    "ai_embeddings": _learning(
        "PATTERN", "AI_ML",
        "Embeddings: Convert text to dense vectors for semantic similarity. Models: OpenAI text-embedding-3-small "
        "(1536d), all-MiniLM-L6-v2 (384d, free). Use cosine similarity for comparison. "
        "Normalize vectors. Batch embed for efficiency. Store in vector DB with metadata.",
        ["OpenAI: openai.embeddings.create(model='text-embedding-3-small', input=texts)",
         "Local: from sentence_transformers import SentenceTransformer; model.encode(texts)",
         "Similarity: cosine_similarity(vec_a, vec_b) → 0.0 to 1.0",
         "Vector DB: ChromaDB (local), Pinecone (cloud), Weaviate, Qdrant"],
        "HIGH", 0.95, times_applied=45,
        context={"applies_to": ["Python"]}
    ),
    "ai_fine_tuning": _learning(
        "PATTERN", "AI_ML",
        "Fine-tuning LLMs: Prepare JSONL training data (prompt/completion pairs). "
        "LoRA/QLoRA for parameter-efficient fine-tuning. Evaluate on held-out test set. "
        "Fine-tune when: Specific domain, consistent format needed, reduce prompt size.",
        ["Data: 100-1000 high-quality examples in JSONL format",
         "LoRA: Fine-tune adapter layers only (4-bit quantized with QLoRA for small GPU)",
         "Eval: Compare fine-tuned vs base model on test set, measure accuracy + latency",
         "When NOT to: Few-shot prompting works, data is insufficient, model already good enough"],
        "MEDIUM", 0.93, times_applied=25,
        context={"applies_to": ["Python"], "tools": ["Hugging Face", "OpenAI API"]}
    ),
    "ai_guardrails": _learning(
        "PATTERN", "AI_ML",
        "AI safety guardrails: Input validation (block prompt injection, PII detection). "
        "Output filtering (toxicity, hallucination detection). Rate limiting per user. "
        "Content moderation API before/after LLM call. Audit log all interactions.",
        ["Input: Detect prompt injection attempts, sanitize user input",
         "Output: Check for PII leakage, toxicity scoring, factual grounding",
         "Moderation: OpenAI moderation endpoint, Perspective API for toxicity",
         "Logging: Log prompt, response, user_id, tokens, latency for audit trail"],
        "CRITICAL", 0.96, times_applied=55,
        context={"applies_to": ["ALL"]}
    ),
    "ai_multi_agent": _learning(
        "PATTERN", "AI_ML",
        "Multi-agent AI systems: Orchestrator agent delegates to specialist agents. "
        "Each agent has specific tools and system prompt. Use message passing between agents. "
        "Frameworks: LangGraph, CrewAI, AutoGen. SupremeAI's consensus voting is a multi-agent pattern.",
        ["Orchestrator: Routes user request to appropriate specialist agent",
         "Specialist: Code agent, research agent, review agent — each with own tools",
         "Communication: Shared memory/context or message queue between agents",
         "SupremeAI: 10-AI consensus voting is a form of multi-agent ensemble"],
        "HIGH", 0.94, times_applied=30,
        context={"applies_to": ["Python", "TypeScript"]}
    ),

    # ── ML Fundamentals ────────────────────────────────────────────────────
    "ai_ml_pipeline": _learning(
        "PATTERN", "AI_ML",
        "ML pipeline: Data collection → Cleaning → Feature engineering → Train/test split (80/20) → "
        "Model training → Evaluation (accuracy, precision, recall, F1) → Deployment → Monitoring. "
        "Version data and models. Use MLflow or Weights & Biases for experiment tracking.",
        ["Split: train_test_split(X, y, test_size=0.2, random_state=42)",
         "Eval: classification_report(y_test, y_pred) for precision/recall/F1",
         "Track: mlflow.log_params(params); mlflow.log_metrics(metrics); mlflow.log_model(model)",
         "Deploy: Serve model via FastAPI endpoint or use TensorFlow Serving"],
        "HIGH", 0.94, times_applied=40,
        context={"applies_to": ["Python"]}
    ),
    "ai_model_evaluation": _learning(
        "PATTERN", "AI_ML",
        "Model evaluation: Classification → accuracy, precision, recall, F1, AUC-ROC. "
        "Regression → MAE, MSE, RMSE, R². Use cross-validation (k-fold) for robust estimates. "
        "Confusion matrix for error analysis. Watch for overfitting (train >> test accuracy).",
        ["Classification: from sklearn.metrics import classification_report, confusion_matrix",
         "Regression: mean_absolute_error, mean_squared_error, r2_score",
         "Cross-val: cross_val_score(model, X, y, cv=5, scoring='accuracy')",
         "Overfitting: Train acc 99% but test acc 70% → reduce model complexity or add regularization"],
        "MEDIUM", 0.94, times_applied=35,
        context={"applies_to": ["Python"]}
    ),

    # ── Data Structures & Algorithms ────────────────────────────────────────
    "dsa_complexity": _learning(
        "PATTERN", "DSA",
        "Time complexity: O(1) constant, O(log n) binary search, O(n) linear, O(n log n) merge sort, "
        "O(n²) nested loops, O(2^n) recursive subsets. Space complexity matters for large data. "
        "Always analyze worst case. Amortized analysis for dynamic arrays and hash tables.",
        ["O(1): HashMap get/put, array index access",
         "O(log n): Binary search, balanced BST operations",
         "O(n log n): Merge sort, Tim sort (Java/Python default)",
         "O(n²): Bubble sort, nested loops — avoid for large n"],
        "HIGH", 0.96, times_applied=90,
        context={"applies_to": ["ALL"]}
    ),
    "dsa_hash_maps": _learning(
        "PATTERN", "DSA",
        "Hash maps: O(1) average lookup/insert/delete. Use for counting, grouping, caching. "
        "Handle collisions (chaining or open addressing). Load factor ~0.75 triggers resize. "
        "In Java: HashMap (unsorted), TreeMap (sorted O(log n)), LinkedHashMap (insertion order).",
        ["Counting: Map<String, Integer> count = new HashMap<>(); items.forEach(i -> count.merge(i, 1, Integer::sum));",
         "Grouping: Map<String, List<Item>> groups = items.stream().collect(Collectors.groupingBy(Item::category));",
         "Two-sum: Use HashMap to find complement in O(n) instead of O(n²)",
         "Python: dict, defaultdict(list), Counter for frequency counting"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["ALL"]}
    ),
    "dsa_trees_graphs": _learning(
        "PATTERN", "DSA",
        "Trees: Binary tree, BST (O(log n) search), AVL/Red-Black (self-balancing), B-Tree (databases). "
        "Traversal: In-order, Pre-order, Post-order, Level-order (BFS). "
        "Graphs: Adjacency list (sparse) vs matrix (dense). BFS for shortest path, DFS for exploration.",
        ["BST search: if (val < node.val) go left, else go right — O(log n) balanced",
         "BFS: Queue-based, level-order traversal, shortest unweighted path",
         "DFS: Stack/recursion, topological sort, cycle detection, connected components",
         "Dijkstra: Shortest weighted path with priority queue — O((V+E) log V)"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["ALL"]}
    ),
    "dsa_sorting_searching": _learning(
        "PATTERN", "DSA",
        "Sorting: Use built-in sort (TimSort O(n log n)) for most cases. Counting sort O(n+k) for "
        "small range integers. Quick sort average O(n log n) but O(n²) worst case. "
        "Binary search: Array must be sorted, O(log n), find target or insertion point.",
        ["Java: Arrays.sort(arr); Collections.sort(list, Comparator.comparing(T::field));",
         "Python: sorted(items, key=lambda x: x.priority, reverse=True)",
         "Binary search: int idx = Collections.binarySearch(sortedList, target);",
         "Python: bisect.insort(sorted_list, item) for maintaining sorted order"],
        "MEDIUM", 0.95, times_applied=65,
        context={"applies_to": ["ALL"]}
    ),
    "dsa_dynamic_programming": _learning(
        "PATTERN", "DSA",
        "Dynamic programming: Break problem into overlapping subproblems. Memoize (top-down) or "
        "tabulate (bottom-up). Classic patterns: Fibonacci, knapsack, LCS, coin change, "
        "grid paths. Identify: optimal substructure + overlapping subproblems.",
        ["Top-down: @lru_cache(maxsize=None) def fib(n): return fib(n-1) + fib(n-2) if n > 1 else n",
         "Bottom-up: dp = [0]*(n+1); dp[1] = 1; for i in range(2, n+1): dp[i] = dp[i-1] + dp[i-2]",
         "Knapsack: dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt[i]] + val[i])",
         "Recognize: 'minimum cost', 'maximum profit', 'number of ways' often signal DP"],
        "MEDIUM", 0.94, times_applied=50,
        context={"applies_to": ["ALL"]}
    ),
    "dsa_stacks_queues": _learning(
        "PATTERN", "DSA",
        "Stack (LIFO): Undo, expression evaluation, DFS, parentheses matching. "
        "Queue (FIFO): BFS, task scheduling, message queues. "
        "Priority Queue (heap): Dijkstra, top-K elements, task prioritization. "
        "Deque: Sliding window, BFS with priority.",
        ["Stack: Deque<Integer> stack = new ArrayDeque<>(); stack.push(val); stack.pop();",
         "Queue: Queue<Integer> queue = new LinkedList<>(); queue.offer(val); queue.poll();",
         "PriorityQueue: PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[0]-b[0]);",
         "Python: from collections import deque; from heapq import heappush, heappop"],
        "MEDIUM", 0.95, times_applied=60,
        context={"applies_to": ["ALL"]}
    ),
}

AI_ML_PATTERNS = {
    "pat_rag_pipeline": _pattern(
        "RAG Pipeline", "AI_ML",
        "Complete Retrieval-Augmented Generation pipeline with embedding, retrieval, and generation",
        "AI-powered search, Q&A systems, knowledge bases",
        "# RAG Pipeline\nfrom langchain.embeddings import OpenAIEmbeddings\nfrom langchain.vectorstores import Chroma\nfrom langchain.chat_models import ChatOpenAI\nfrom langchain.chains import RetrievalQA\n\n# 1. Embed & Store\nembeddings = OpenAIEmbeddings()\nvectordb = Chroma.from_documents(docs, embeddings, persist_directory='./chroma_db')\n\n# 2. Retrieve & Generate\nretriever = vectordb.as_retriever(search_kwargs={'k': 5})\nllm = ChatOpenAI(model='gpt-4', temperature=0)\nqa_chain = RetrievalQA.from_chain_type(llm, retriever=retriever)\n\n# 3. Query\nresult = qa_chain.invoke({'query': 'How does the auth system work?'})",
        "Python + LangChain", 0.95, times_used=40
    ),
    "pat_llm_service": _pattern(
        "LLM Service with Retry", "AI_ML",
        "Production LLM service wrapper with caching, retry, and token tracking",
        "Any application using LLM APIs",
        "@Service\npublic class LLMService {\n  private final WebClient client;\n  private final Cache<String, String> cache = Caffeine.newBuilder().maximumSize(1000).expireAfterWrite(1, TimeUnit.HOURS).build();\n  \n  @Retryable(maxAttempts=3, backoff=@Backoff(delay=1000, multiplier=2))\n  public String generate(String systemPrompt, String userPrompt) {\n    String cacheKey = DigestUtils.sha256Hex(systemPrompt + userPrompt);\n    String cached = cache.getIfPresent(cacheKey);\n    if (cached != null) return cached;\n    \n    String response = client.post().uri(\"/chat/completions\")\n      .bodyValue(Map.of(\"model\", \"gpt-4\", \"messages\", List.of(\n        Map.of(\"role\", \"system\", \"content\", systemPrompt),\n        Map.of(\"role\", \"user\", \"content\", userPrompt)\n      ), \"temperature\", 0))\n      .retrieve().bodyToMono(String.class).block();\n    cache.put(cacheKey, response);\n    return response;\n  }\n}",
        "Spring Boot", 0.95, times_used=35
    ),
    "pat_binary_search": _pattern(
        "Binary Search Template", "DSA",
        "Versatile binary search template for finding target or boundary",
        "Sorted arrays, search problems, finding boundaries",
        "// Find target or insertion point\nint binarySearch(int[] arr, int target) {\n  int lo = 0, hi = arr.length - 1;\n  while (lo <= hi) {\n    int mid = lo + (hi - lo) / 2;  // avoid overflow\n    if (arr[mid] == target) return mid;\n    else if (arr[mid] < target) lo = mid + 1;\n    else hi = mid - 1;\n  }\n  return lo;  // insertion point\n}\n\n// Python: bisect_left equivalent\ndef binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n    while lo <= hi:\n        mid = (lo + hi) // 2\n        if arr[mid] < target: lo = mid + 1\n        else: hi = mid - 1\n    return lo",
        "Java / Python", 0.96, times_used=70
    ),
    "pat_graph_bfs_dfs": _pattern(
        "BFS & DFS Templates", "DSA",
        "Standard BFS and DFS graph traversal templates",
        "Graph problems, tree traversal, shortest path",
        "// BFS — shortest path in unweighted graph\nvoid bfs(Map<Integer, List<Integer>> graph, int start) {\n  Queue<Integer> queue = new LinkedList<>();\n  Set<Integer> visited = new HashSet<>();\n  queue.offer(start); visited.add(start);\n  while (!queue.isEmpty()) {\n    int node = queue.poll();\n    for (int neighbor : graph.getOrDefault(node, List.of())) {\n      if (visited.add(neighbor)) queue.offer(neighbor);\n    }\n  }\n}\n\n// DFS — recursive\nvoid dfs(Map<Integer, List<Integer>> graph, int node, Set<Integer> visited) {\n  visited.add(node);\n  for (int neighbor : graph.getOrDefault(node, List.of())) {\n    if (!visited.contains(neighbor)) dfs(graph, neighbor, visited);\n  }\n}",
        "Java", 0.96, times_used=60
    ),
}
