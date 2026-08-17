# Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common issues when developing or running SupremeAI 2.0.

## Common Issues

### 1. Backend Won't Start

**Symptom**: `uvicorn main:app --reload` fails with an error.

**Possible Causes & Solutions**:

#### Missing Environment Variables

```
Error: [FATAL] Missing critical environment variables: GEMINI_API_KEY
```

**Solution**: Copy `.env.example` to `.env` and fill in all required values:

```bash
cp backend/.env.example backend/.env
```

#### Port Already in Use

```
Error: Address already in use
```

**Solution**: Kill the process using port 8000:

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
```

#### Redis Connection Failed

```
Error: Could not connect to Redis
```

**Solution**: Ensure Redis is running:

```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Or check if Upstash URL is correct in .env
```

### 2. Frontend Build Errors

**Symptom**: `pnpm dev` or `pnpm build` fails.

#### Dependency Issues

```
Error: Cannot find module '@supremeai/shared-types'
```

**Solution**: Reinstall dependencies:

```bash
pnpm install --frozen-lockfile
```

#### TypeScript Errors

```
error TS2307: Cannot find module or its corresponding type declarations
```

**Solution**: Regenerate type definitions:

```bash
pnpm turbo run build --filter=shared-types
```

### 3. Authentication Issues

#### JWT Token Invalid

**Symptom**: API returns 401 Unauthorized.

**Solution**: Clear cookies and re-authenticate. If the issue persists, check JWT secret configuration:

```bash
# Ensure JWT_SECRET is set in .env
echo $JWT_SECRET
```

#### JIT OTP Not Received

**Symptom**: OTP not delivered for sensitive operations.

**Solution**: Check Discord webhook or Resend email configuration:

```bash
# Verify Discord webhook URL
echo $DISCORD_WEBHOOK_URL

# Verify Resend API key
echo $RESEND_API_KEY
```

### 4. API Rate Limiting

**Symptom**: API returns 429 Too Many Requests.

**Solution**:
- Wait for the rate limit window to reset
- Use the multi-model routing to distribute load
- Check if you're hitting the correct rate limits

### 5. Database Migration Issues

**Symptom**: Database errors on startup.

**Solution**: Run migrations:

```bash
cd backend
poetry run alembic upgrade head
```

### 6. Docker Issues

#### Container Won't Start

```
Error: OCI runtime create failed
```

**Solution**: Check Docker resources and restart Docker Desktop.

#### Image Build Fails

```
Error: failed to solve
```

**Solution**: Check `.dockerignore` and ensure no sensitive files are included:

```bash
# Verify .env files are excluded
cat .dockerignore
```

## Diagnostic Commands

### Check System Health

```bash
# Backend health check
curl http://localhost:8000/health

# Aggregated health check
curl http://localhost:8000/health/aggregated

# Frontend health check
curl -I http://localhost:5173
```

### Check Logs

```bash
# Backend logs
pnpm backend:dev

# Frontend logs
cd apps/studio-client
pnpm dev

# Docker logs
docker-compose logs -f
```

### Run Diagnostics

```bash
# Full system diagnostics
python scripts/diagnostics.py

# Check environment
python scripts/bootstrap_env.py

# Verify secrets
python scripts/check_secrets.py
```

## Getting Help

If you can't find a solution here:

1. **Search GitHub Issues**: Check if the issue has been reported
2. **Discord**: Join our Discord server for real-time help
3. **GitHub Discussions**: Ask the community
4. **Create an Issue**: If it's a new bug, create a detailed issue

## Log Levels

| Level | Description | When to Use |
|-------|-------------|-------------|
| `DEBUG` | Detailed diagnostic information | Development only |
| `INFO` | General operational messages | Normal operation |
| `WARNING` | Something unexpected, but not serious | Potential issues |
| `ERROR` | A serious problem, some functionality failed | Errors |
| `CRITICAL` | A very serious error, system may be unusable | System failures |
