# SupremeAI MCP Control Tower — multi-stage Docker build
# Build context: infrastructure/mcp-control-plane/ (per docker-compose.yml and CI).
# Runtime: node dist/index.js — Streamable-HTTP MCP server.
# Port: MCP_PORT (default 3771). Health: GET /health -> 200 JSON (see src/index.ts).
# All runtime imports (src/lib/**, src/tools/**, src/policy/**, src/events/**,
# src/remediation/**) compile into dist/ via tsc (tsconfig: rootDir=src, outDir=dist),
# so the runtime image needs only dist/ + production dependencies.
# Test scripts (test_*.ts) live at package root and are excluded by tsconfig — see .dockerignore.
#
# Task 4 fix (2026-09-19): Added Python 3 + uv to the runtime stage so the
# MemorySubAdapter can spawn the Python memory sidecar (backend/memory/mcp_server.py)
# via StdioClientTransport. Without these runtimes the Tower returned ENOENT on every
# memory.* tool call. The backend/ code is expected to be mounted or present at
# SUPREMEAI_BACKEND_DIR (default: ../../../../backend relative to dist/).

# ── Stage 1: builder (Node/TypeScript) ────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

# Install the exact dependency tree first (typescript is a devDependency, used here)
COPY package.json package-lock.json ./
RUN npm ci

# Compile TypeScript -> dist/
COPY tsconfig.json ./
COPY src/ ./src/
RUN npm run build

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production

# ── Python 3 + uv (needed for memory sidecar: backend/memory/mcp_server.py) ──
# python3, pip3, and curl for uv installer. Keep the layer small with --no-cache.
RUN apk add --no-cache python3 py3-pip curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
    && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

# Verify Python + uv are accessible
RUN python3 --version && uv --version

COPY --from=builder /app/dist ./dist
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

# backend/ Python source is NOT copied into the image here.
# For Docker compose: backend/ is volume-mounted at /app/backend at runtime
#   (see docker-compose.yml mcp.volumes) so uv can spawn the memory sidecar.
# For Render native (env: node): Render checks out the full repo; uv is installed
#   via `pip install uv` in buildCommand (render.yaml), and SUPREMEAI_BACKEND_DIR
#   env var points the adapter to the correct path.

RUN chown -R node:node /app

USER node

EXPOSE 3771

# busybox wget ships with alpine; /health returns HTTP 200 (src/index.ts)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3771/health || exit 1

CMD ["node", "dist/index.js"]

