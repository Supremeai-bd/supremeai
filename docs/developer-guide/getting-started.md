# Getting Started with SupremeAI 2.0

## Overview

This guide walks you through setting up a local development environment for SupremeAI 2.0, a multi-cloud AI orchestration platform built on FastAPI with a React/Vite frontend.

## Prerequisites

- **Node.js**: >= 20.0.0
- **pnpm**: >= 9.0.0
- **Python**: >= 3.10
- **Docker Desktop**: For containerized services (Redis, databases)
- **Google Cloud SDK** (optional, for GCP deployment)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/SaifulHaqueNiloy/supremeai.git
cd supremeai
```

### 2. Install Dependencies

```bash
# Install frontend dependencies
pnpm install --frozen-lockfile

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit backend/.env with your API keys
# Required: GEMINI_API_KEY, OPENAI_API_KEY, FIRESTORE_CREDENTIALS
```

### 4. Start Services

```bash
# Backend (FastAPI)
cd backend
uvicorn main:app --reload --port 8000
# Access API docs at http://localhost:8000/docs

# Frontend (Web Studio Client)
cd apps/studio-client
pnpm dev
# Access at http://localhost:5173

# Mobile App (Flutter)
cd apps/mobile
flutter pub get
flutter run
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `DEEPSEEK_API_KEY` | No | DeepSeek API key (fallback) |
| `GROQ_API_KEY` | No | Groq API key (fallback) |
| `REDIS_URL` | Yes | Redis connection string |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ENV` | No | `local` or `production` (default: `local`) |

## Next Steps

- [Architecture Overview](architecture.md)
- [API Documentation](../api/v1/authentication.md)
- [Coding Standards](coding-standards.md)
- [Testing Guide](testing.md)
