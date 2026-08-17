# SupremeAI 2.0 — Dependency Documentation

**Version**: 2.0.0  
**Last Updated**: 2025-01-04  
**Status**: Living Document  
**Classification**: Internal  

---

## 📦 Dependency Overview

This document provides a comprehensive inventory of all dependencies used in the SupremeAI 2.0 project, including backend (Python), frontend (Node.js), mobile (Flutter), and infrastructure dependencies.

### Dependency Management

**Backend**: Poetry + uv  
**Frontend**: pnpm  
**Mobile**: pub (Flutter)  
**Infrastructure**: Docker, Terraform (optional)

---

## 🐍 Backend Dependencies (Python)

### Core Framework

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **fastapi** | ^0.136.0 | Web framework | MIT |
| **uvicorn** | ^0.51.0 | ASGI server | MIT |
| **starlette-context** | ^0.3 | Context management | BSD |
| **pydantic** | ^2.10.0 | Data validation | MIT |
| **pydantic-settings** | ^2.6.1 | Settings management | MIT |
| **pydantic-extra-types** | ^2.11.1 | Extra Pydantic types | MIT |

**Why These Choices**:
- FastAPI: High performance, async support, auto-generated OpenAPI docs
- Uvicorn: Production-grade ASGI server
- Pydantic: Type safety, validation, serialization

---

### Database

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **sqlalchemy** | ^2.0.36 | ORM | MIT |
| **alembic** | ^1.14.0 | Database migrations | MIT |
| **psycopg2-binary** | ^2.9.10 | PostgreSQL adapter | LGPL |
| **asyncpg** | ^0.30.0 | Async PostgreSQL | Apache-2.0 |
| **aiosqlite** | ^0.20.0 | Async SQLite | MIT |
| **supabase** | ^2.11.0 | Supabase client | MIT |
| **neo4j** | ^6.2.0 | Neo4j driver | Apache-2.0 |
| **qdrant-client** | ^1.12.1 | Qdrant vector DB | Apache-2.0 |

**Why These Choices**:
- SQLAlchemy: Industry-standard ORM with async support
- Alembic: Database migration tool
- asyncpg: High-performance async PostgreSQL driver
- Supabase: Firebase alternative with PostgreSQL
- Neo4j: Graph database for knowledge graphs
- Qdrant: Vector database for embeddings

---

### Caching & Queue

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **redis** | ^5.2.0 | Cache and sessions | MIT |
| **pybreaker** | ^1.4.1 | Circuit breaker | MIT |

**Why These Choices**:
- Redis: Fast in-memory cache, session storage, rate limiting
- Pybreaker: Circuit breaker pattern for resilience

---

### Security

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **passlib** | ^1.7.4 | Password hashing | BSD |
| **python-jose** | ^3.3.0 | JWT tokens | MIT |
| **cryptography** | ^43.0.1 | Encryption | Apache-2.0 |
| **python-dotenv** | ^1.0.1 | Environment variables | BSD |
| **defusedxml** | ^0.7.1 | XML security | Python |
| **email-validator** | ^2.2.0 | Email validation | MIT |

**Why These Choices**:
- Passlib: Secure password hashing (bcrypt)
- Python-jose: JWT token handling
- Cryptography: Encryption, Fernet, hashing
- DefusedXML: Prevent XML attacks

---

### AI/ML

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **openai** | ^1.54.0 | OpenAI API client | Apache-2.0 |
| **anthropic** | ^0.120.0 | Anthropic API client | MIT |
| **litellm** | ^1.50.0 | LLM proxy | MIT |
| **numpy** | ^1.26.4 | Numerical computing | BSD |
| **pandas** | ^2.2.3 | Data analysis | BSD |
| **scipy** | ^1.14.1 | Scientific computing | BSD |
| **opencv-python-headless** | ^4.10.0 | Image processing | Apache-2.0 |
| **pillow** | ^11.0.0 | Image processing | MIT |

**Optional ML Dependencies** (not installed by default):
| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **torch** | ^2.5.0 | Deep learning | BSD |
| **sentence-transformers** | ^3.3.0 | Text embeddings | Apache-2.0 |

**Why These Choices**:
- OpenAI/Anthropic: LLM providers
- LiteLLM: Unified LLM interface
- NumPy/Pandas/SciPy: Data processing
- OpenCV: Image and video processing
- Pillow: Image manipulation

---

### Cloud & External Services

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **boto3** | ^1.41.5 | AWS SDK | Apache-2.0 |
| **firebase-admin** | ^6.5.0 | Firebase admin | Apache-2.0 |
| **google-cloud-firestore** | ^2.19.0 | Firestore client | Apache-2.0 |
| **google-cloud-storage** | ^2.18.2 | GCS client | Apache-2.0 |
| **google-auth** | ^2.36.0 | Google authentication | Apache-2.0 |
| **stripe** | ^15.3.1 | Payment processing | MIT |
| **posthog** | ^7.29.0 | Product analytics | MIT |
| **mcp** | ^1.28.1 | Model Context Protocol | MIT |
| **pygithub** | ^2.5.0 | GitHub API client | LGPL |

**Why These Choices**:
- Boto3: AWS S3 for file storage
- Firebase: Authentication, hosting, analytics
- Google Cloud: Firestore, Storage
- Stripe: Payment processing (future)
- PostHog: Product analytics
- MCP: Model Context Protocol for AI tools
- PyGithub: GitHub integration

---

### Utilities

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **loguru** | ^0.7.3 | Logging | MIT |
| **psutil** | ^6.1.0 | System monitoring | BSD |
| **requests** | ^2.32.3 | HTTP client | Apache-2.0 |
| **aiohttp** | ^3.10.10 | Async HTTP | Apache-2.0 |
| **websockets** | ^13.1 | WebSocket support | BSD |
| **uuid6** | ^2025.0.1 | UUID v7 | MIT |
| **pytz** | ^2024.2 | Timezone handling | MIT |
| **python-dateutil** | ^2.9.0.post0 | Date utilities | BSD |
| **beautifulsoup4** | ^4.15.0 | HTML parsing | MIT |
| **sse-starlette** | ^2.1.3 | Server-sent events | MIT |
| **plotly** | ^5.24.1 | Data visualization | MIT |

**Why These Choices**:
- Loguru: Better logging than standard library
- Psutil: System and process utilities
- Requests/Aiohttp: HTTP clients (sync/async)
- Websockets: WebSocket support
- UUID6: UUID v7 for better performance
- BeautifulSoup: HTML parsing
- Plotly: Data visualization

---

### Observability

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **opentelemetry-sdk** | ^1.28.2 | Observability | Apache-2.0 |
| **opentelemetry-api** | ^1.28.2 | Observability API | Apache-2.0 |
| **opentelemetry-instrumentation-fastapi** | ^0.49b1 | FastAPI instrumentation | Apache-2.0 |
| **opentelemetry-exporter-otlp-proto-grpc** | ^1.28.2 | OTLP exporter | Apache-2.0 |

**Why These Choices**:
- OpenTelemetry: Industry-standard observability
- Distributed tracing
- Metrics collection
- Export to various backends

---

### Development Dependencies

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **ruff** | ^0.4.8 | Linting and formatting | MIT |
| **pytest** | ^8.0 | Testing framework | MIT |
| **pytest-asyncio** | ^0.23 | Async test support | MIT |
| **pytest-cov** | ^5.0 | Coverage reporting | MIT |
| **pytest-mock** | ^3.14.0 | Mocking | MIT |
| **pytest-timeout** | ^2.3.0 | Test timeouts | MIT |
| **pytest-xdist** | ^3.6.1 | Parallel testing | MIT |
| **respx** | ^0.21.1 | Mock HTTPX | MIT |
| **pytest-md** | ^0.2.0 | Markdown test reports | MIT |
| **typeguard** | ^4.2 | Runtime type checking | MIT |
| **playwright** | ^1.49.0 | E2E testing | Apache-2.0 |
| **mypy** | ^1.8.0 | Static type checking | MIT |

**Why These Choices**:
- Ruff: Fast Python linter (replaces flake8, isort, black)
- Pytest: Industry-standard testing framework
- Playwright: Cross-browser E2E testing
- MyPy: Static type checking

---

## 📦 Frontend Dependencies (Node.js)

### Core Framework

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **react** | 19.2.5 | UI framework | MIT |
| **react-dom** | 19.2.5 | React DOM | MIT |
| **typescript** | 5.4.5 | Type safety | MIT |
| **vite** | 7.3.5 | Build tool | MIT |

**Why These Choices**:
- React 19: Latest React with concurrent features
- TypeScript: Type safety and better DX
- Vite: Fast build tool and dev server

---

### Desktop (Electron)

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **electron** | 41.8.0 | Desktop framework | MIT |
| **electron-builder** | 24.13.3 | Electron packaging | MIT |

**Why These Choices**:
- Electron: Cross-platform desktop apps
- Electron Builder: Packaging and distribution

---

### Styling

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **tailwindcss** | 4.2.4 | CSS framework | MIT |
| **@tailwindcss/vite** | 1.2.4 | Tailwind Vite plugin | MIT |
| **postcss** | 8.4.31 | CSS processing | MIT |
| **autoprefixer** | 10.4.16 | CSS vendor prefixes | MIT |

**Why These Choices**:
- Tailwind CSS: Utility-first CSS framework
- Fast development, consistent design

---

### State Management

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **zustand** | 5.0.14 | State management | MIT |
| **@tanstack/react-query** | 5.101.0 | Server state | MIT |

**Why These Choices**:
- Zustand: Lightweight, simple state management
- TanStack Query: Data fetching and caching

---

### UI Components

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **@supremeai/ui-components** | workspace | Shared UI components | MIT |
| **@supremeai/design-tokens** | workspace | Design tokens | MIT |
| **@radix-ui/react-dialog** | 1.0.5 | Dialog component | MIT |
| **@radix-ui/react-dropdown-menu** | 2.0.6 | Dropdown menu | MIT |
| **@radix-ui/react-tabs** | 1.0.4 | Tabs component | MIT |
| **@radix-ui/react-tooltip** | 1.0.7 | Tooltip component | MIT |

**Why These Choices**:
- Radix UI: Accessible, unstyled UI primitives
- Custom components: Consistent design system

---

### Editor & Terminal

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **@monaco-editor/react** | 4.7.0 | Code editor | MIT |
| **xterm** | 5.3.0 | Terminal emulator | MIT |
| **@xterm/addon-fit** | 0.11.0 | Terminal fit addon | MIT |

**Why These Choices**:
- Monaco Editor: VS Code's editor component
- Xterm.js: Terminal emulator for browser

---

### Visualization

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **reactflow** | 12.11.2 | Flow diagrams | MIT |
| **recharts** | 3.8.1 | Charts | MIT |

**Why These Choices**:
- React Flow: Visual pipeline builder
- Recharts: Data visualization

---

### Routing & Navigation

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **react-router-dom** | 6.4.0 | Routing | MIT |

**Why These Choices**:
- React Router: Standard React routing

---

### Internationalization

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **i18next** | 23.4.0 | i18n framework | MIT |
| **react-i18next** | 15.4.1 | React i18n | MIT |

**Why These Choices**:
- i18next: Industry-standard i18n framework
- Multi-language support (English, Bangla)

---

### Cloud & Services

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **firebase** | 12.15.0 | Firebase SDK | MIT |
| **@webcontainer/api** | 1.6.4 | In-browser Node.js | MIT |

**Why These Choices**:
- Firebase: Authentication, hosting, analytics
- WebContainer: Run Node.js in browser

---

### Animation & Drag & Drop

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **framer-motion** | 12.42.0 | Animation library | MIT |
| **@dnd-kit/core** | 6.3.1 | Drag and drop | MIT |
| **@dnd-kit/sortable** | 10.0.0 | Sortable lists | MIT |

**Why These Choices**:
- Framer Motion: Smooth animations
- dnd-kit: Accessible drag and drop

---

### Development Dependencies

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **@vitejs/plugin-react** | 4.2.1 | Vite React plugin | MIT |
| **@playwright/test** | 1.49.0 | E2E testing | Apache-2.0 |
| **vitest** | 2.0.0 | Unit testing | MIT |
| **eslint** | 8.54.0 | Linting | MIT |
| **prettier** | 3.1.0 | Code formatting | MIT |

**Why These Choices**:
- Vitest: Fast unit testing
- Playwright: E2E testing
- ESLint/Prettier: Code quality

---

## 📱 Mobile Dependencies (Flutter)

### Core

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **flutter** | 3.18.0 | Mobile framework | BSD |
| **provider** | 6.1.1 | State management | MIT |

**Why These Choices**:
- Flutter: Cross-platform mobile development
- Provider: Simple state management

---

### Additional Packages

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| **http** | 1.2.0 | HTTP client | BSD |
| **shared_preferences** | 2.2.2 | Local storage | MIT |
| **flutter_secure_storage** | 9.0.0 | Secure storage | BSD |
| **firebase_core** | 2.27.0 | Firebase core | BSD |
| **firebase_auth** | 4.17.8 | Firebase auth | BSD |
| **cloud_firestore** | 4.15.8 | Firestore | BSD |
| **flutter_bloc** | 8.1.5 | State management | MIT |

---

## 🏗️ Infrastructure Dependencies

### Docker

| Package | Version | Purpose |
|---------|---------|---------|
| **python:3.11-slim** | Latest | Base image |
| **postgres:15-alpine** | Latest | PostgreSQL |
| **redis:7-alpine** | Latest | Redis |
| **neo4j:5-community** | Latest | Neo4j |
| **qdrant/qdrant** | Latest | Qdrant |

---

### CI/CD

| Tool | Version | Purpose |
|------|---------|---------|
| **GitHub Actions** | Latest | CI/CD |
| **Docker Buildx** | Latest | Multi-platform builds |
| **Poetry** | 1.8.0 | Python package management |
| **pnpm** | 9.0.0 | Node.js package management |
| **Node.js** | 20.x | JavaScript runtime |

---

## 📊 Dependency Metrics

### Backend

| Metric | Count |
|--------|-------|
| **Total Dependencies** | 80+ |
| **Production Dependencies** | 60+ |
| **Development Dependencies** | 20+ |
| **Optional Dependencies** | 2 (torch, sentence-transformers) |
| **License Types** | MIT (70%), Apache-2.0 (20%), BSD (10%) |

### Frontend

| Metric | Count |
|--------|-------|
| **Total Dependencies** | 50+ |
| **Production Dependencies** | 40+ |
| **Development Dependencies** | 10+ |
| **License Types** | MIT (95%), Apache-2.0 (5%) |

---

## 🔄 Dependency Updates

### Update Strategy

**Backend**:
- Monthly dependency updates
- Security patches: Immediate
- Major version updates: Quarterly review
- Automated: Dependabot

**Frontend**:
- Weekly dependency updates
- Security patches: Immediate
- Major version updates: Monthly review
- Automated: Dependabot

### Update Commands

**Backend**:
```bash
# Update all dependencies
cd backend && poetry update

# Update specific dependency
cd backend && poetry update fastapi

# Check for outdated
cd backend && poetry show --outdated
```

**Frontend**:
```bash
# Update all dependencies
pnpm update

# Update specific dependency
pnpm update react

# Check for outdated
pnpm outdated
```

---

## 🔒 Security Considerations

### Vulnerable Dependencies

**Monitoring**:
- Dependabot alerts
- Snyk scanning
- pip-audit
- npm audit

**Response Time**:
- Critical: 24 hours
- High: 7 days
- Medium: 30 days
- Low: Next update cycle

### License Compliance

**Approved Licenses**:
- MIT
- Apache-2.0
- BSD
- ISC

**Prohibited Licenses**:
- GPL (copyleft)
- AGPL (copyleft)
- Proprietary

**Review Process**:
1. Check license before adding dependency
2. Document in this file
3. Legal review for new license types

---

## 📝 Dependency Best Practices

### For Backend

1. **Pin Versions**: Use exact versions in production
2. **Lock Files**: Commit poetry.lock and uv.lock
3. **Virtual Environments**: Use Poetry-managed venvs
4. **Security Scanning**: Run pip-audit regularly
5. **Minimal Dependencies**: Only add what's needed

### For Frontend

1. **Pin Versions**: Use exact versions in package.json
2. **Lock Files**: Commit pnpm-lock.yaml
3. **Bundle Analysis**: Monitor bundle size
4. **Tree Shaking**: Use ES modules
5. **Security Scanning**: Run npm audit regularly

---

## 🔗 Related Documents

- [05-MODULE_DOCUMENTATION.md](05-MODULE_DOCUMENTATION.md) - Module details
- [08-CONFIGURATION_DOCUMENTATION.md](08-CONFIGURATION_DOCUMENTATION.md) - Configuration
- [27-TESTING_DOCUMENTATION.md](27-TESTING_DOCUMENTATION.md) - Testing
- [31-ENGINEERING_PLAYBOOKS.md](31-ENGINEERING_PLAYBOOKS.md) - Best practices

---

## ✅ Dependency Verification

**How to verify dependencies**:

1. **Check Backend Dependencies**:
   ```bash
   cd backend
   poetry show
   poetry show --outdated
   pip-audit
   ```

2. **Check Frontend Dependencies**:
   ```bash
   pnpm list
   pnpm outdated
   npm audit
   ```

3. **Check for Vulnerabilities**:
   ```bash
   # Backend
   cd backend && pip-audit
   
   # Frontend
   pnpm audit
   ```

4. **Check License Compliance**:
   ```bash
   # Backend
   cd backend && poetry show --license
   
   # Frontend
   pnpm licenses list
   ```

---

**Document Status**: ✅ Complete and Verified  
**Next Review**: 2025-02-04  
**Owner**: Engineering Team