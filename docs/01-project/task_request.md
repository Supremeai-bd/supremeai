# SupremeAI Task Request: Code Robustness & Health Details Endpoint

Please perform the following tasks:

1. **Fix Codebase Crash (Router Import Guards):**
   In `backend/core/app.py`, many routers imported from `api.routes` can be `None` if they fail to import due to external dependencies.
   - Wrap all unprotected `app.include_router(router_name)` calls in `if router_name is not None:` blocks.
   - This ensures the API starts up correctly even if some modules (like Database, PostHog, or SSO) are not fully configured.

2. **Implement New Feature (Detailed Health Endpoint):**
   - Create a new endpoint `GET /health/details` in `backend/core/app.py` (or as a separate router if appropriate).
   - This endpoint must return system statistics:
     - Python Version
     - CPU Count
     - Platform OS info
     - Memory info (if possible, or simple CPU load stub)
   - Ensure the endpoint is properly documented with FastAPI description.

3. **Verify:**
   - Run the pytest test suite using your environment to ensure everything loads and passes.
