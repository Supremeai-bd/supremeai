# বাংলা: পাতলা গেটওয়ে ইমেজ — কোনো secret ইমেজ-স্তরে নয়, সব runtime-env
FROM python:3.12-slim
WORKDIR /app

# Render injects RENDER_GIT_COMMIT as a build arg for Docker services.
# Bake it into the runtime env so /release can report the running commit SHA.
ARG RENDER_GIT_COMMIT=""
ENV RENDER_GIT_COMMIT=${RENDER_GIT_COMMIT} GIT_COMMIT=${RENDER_GIT_COMMIT} PYTHONUNBUFFERED=1

# Audit 2026-11-19 (#6): the image previously ran as root. Create an
# unprivileged runtime identity before any COPY so ownership is explicit.
RUN addgroup --system supremeai && adduser --system supremeai --ingroup supremeai

# Use the reviewed resolution from the monorepo-root build context.
# Dependency installation must succeed; never resolve a floating fallback.
COPY gateway/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock

COPY --chown=supremeai:supremeai gateway/contracts/ contracts/
COPY --chown=supremeai:supremeai gateway/config/ config/

# বাংলা: #1772 মূল-কারণ সংশোধন — অ্যাপ নিজের কোডকে `gateway.*` নেমস্পেস হিসেবে
# ইমপোর্ট করে (app.py সহ ১৬+ ইমপোর্ট-সাইট; correlation_id/security_headers সহ)।
# পুরনো flat `service/` লেআউটে `uvicorn service.app:app` বুটেই ImportError করত —
# এখন থেকে প্যাকেজ-সত্য লেআউট: gateway/ প্যাকেজ হিসেবেই শিপ হবে, রানও সেভাবেই।
COPY --chown=supremeai:supremeai gateway/ gateway/

COPY --chown=supremeai:supremeai scripts/runtime/infisical_bootstrap.py runtime/infisical_bootstrap.py

USER supremeai
EXPOSE 8787

# Audit 2026-11-19 (#6): Render can now detect a hung process from inside the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; p=os.getenv('PORT','8787'); urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=4)" || exit 1

# Audit 2026-11-19 (#5): fail-closed vault bootstrap. The old `|| uvicorn ...`
# fallback silently started a secretless gateway when a configured Infisical
# was unreachable. `exec` keeps PID 1 as the app process (#6); the bootstrap
# itself starts the app normally when no vault is configured (local/dev).
CMD ["sh", "-c", "exec python runtime/infisical_bootstrap.py uvicorn gateway.service.app:app --host 0.0.0.0 --port ${PORT:-8787}"]
