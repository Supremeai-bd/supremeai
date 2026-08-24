import os

def check_file_contains(filepath, search_str):
    if not os.path.exists(filepath): return False
    with open(filepath, 'r', encoding='utf-8') as f:
        return search_str in f.read()

checks = {
    "#1 recall_memories user filter": ("backend/services/memory_service.py", '"user_id_filter": user_id'),
    "#2 get_memories ignores user_id": ("backend/services/memory_service.py", 'session_id=f"{user_id}/%"'),
    "#6 FreeTierTracker global singleton": ("backend/core/llm/free_tier_tracker.py", 'user_id: str | None = None'),
    "#7 TokenBudgetManager global singleton": ("backend/core/llm/token_budget.py", 'user_id: str | None = None'),
    "#11 RateLimitMiddleware check order": ("backend/core/rate_limit.py", 'if not allowed:\n            return JSONResponse'),
    "#15 db_session contextmanager sync on async": ("backend/core/db.py", '@asynccontextmanager'),
    "#16 rate_limit_store unbounded dict": ("backend/api/server.py", 'rate_limit_store.clear()'),
    "#26 WebSocket chat_history OOM": ("backend/api/routes/websocket_agent.py", 'chat_history[:] = chat_history[-MAX_CHAT_HISTORY:]'),
    "#31 SQLite opened per-operation locking": ("backend/core/evolution/evolution_engine.py", 'self._sqlite_lock = threading.Lock()'),
    "#38 CircuitStats consecutive_failures": ("backend/core/circuit_breaker.py", 'self._stats.consecutive_successes += 1')
}

print("Checking patched status of selected issues:")
for issue, (path, patch_str) in checks.items():
    is_patched = check_file_contains(path, patch_str)
    print(f"{issue}: {'FIXED' if is_patched else 'NOT FIXED'}")
