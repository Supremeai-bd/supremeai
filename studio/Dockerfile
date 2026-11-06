# Multi-stage Dockerfile for SupremeAI Studio (Vite + React SPA)
# Aligns with pure root Vite workspace layout (src/, packages/, public/, nginx.conf)
FROM node:22-alpine AS builder
WORKDIR /app

# Enable corepack for pnpm
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate

# Copy root manifest and workspace dependencies
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
COPY packages/ ./packages/

# Install dependencies (frozen-lockfile for deterministic builds)
RUN pnpm install --frozen-lockfile

# Copy application source code
COPY public/ ./public/
COPY src/ ./src/
COPY index.html tsconfig*.json vite.config.ts tailwind.config.js ./

# Build production SPA assets
ARG VITE_API_URL=""
ARG VITE_USE_RELATIVE_PATH=true
ENV VITE_API_URL=$VITE_API_URL \
    VITE_BACKEND_URL=$VITE_API_URL \
    VITE_USER_BACKEND=$VITE_API_URL \
    VITE_ADMIN_BACKEND=$VITE_API_URL \
    VITE_USE_RELATIVE_PATH=$VITE_USE_RELATIVE_PATH \
    NODE_ENV=production

RUN pnpm run build

# Stage 2: Serve with lightweight Nginx
FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Setup non-root execution permissions for nginx user
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && chown -R nginx:nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid

USER nginx
EXPOSE 80 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
