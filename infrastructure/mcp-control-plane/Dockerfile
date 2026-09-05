# SupremeAI MCP Control Tower — multi-stage Docker build
# Build context: infrastructure/mcp-control-plane/
# Runtime: node dist/index.js — Streamable-HTTP MCP server.
# Port: MCP_PORT (default 3771). Health: GET /health -> 200 JSON (see src/index.ts).
# All runtime imports (src/lib/**, src/tools/**, src/policy/**, src/events/**,
# src/remediation/**) compile into dist/ via tsc (tsconfig: rootDir=src, outDir=dist),
# so the runtime image needs only dist/ + production dependencies.
# Test scripts (test_*.ts) live at package root and are excluded by tsconfig — see .dockerignore.

# ── Stage 1: builder ──────────────────────────────────────────────────────────
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

COPY --from=builder /app/dist ./dist
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force \
    && chown -R node:node /app

USER node

EXPOSE 3771

# busybox wget ships with alpine; /health returns HTTP 200 (src/index.ts)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3771/health || exit 1

CMD ["node", "dist/index.js"]
