"""
Part 6: DevOps & CI/CD Knowledge
Covers: Docker, Kubernetes, GitHub Actions, Terraform, monitoring, logging, cloud deployment
~25 learnings + ~15 patterns + ~10 templates = 50 documents
"""
from seed_data.helpers import _learning, _pattern, _code_template

DEVOPS_LEARNINGS = {

    # ── Docker ─────────────────────────────────────────────────────────────
    "devops_docker_best_practices": _learning(
        "PATTERN", "DOCKER",
        "Docker best practices: Multi-stage builds to reduce image size. Use .dockerignore. "
        "Non-root user. Pin base image versions. COPY before RUN for layer caching. "
        "One process per container. HEALTHCHECK for orchestrators.",
        ["Multi-stage: FROM node:20-alpine AS build; RUN npm ci && npm run build; FROM nginx:alpine; COPY --from=build /app/dist /usr/share/nginx/html",
         "Non-root: RUN addgroup -S app && adduser -S app -G app; USER app",
         "Layer cache: COPY package*.json ./ → RUN npm ci → COPY . . (source changes don't bust dep cache)",
         "HEALTHCHECK --interval=30s CMD wget -qO- http://localhost:8080/health || exit 1"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["Docker", "ALL"]}
    ),
    "devops_docker_compose": _learning(
        "PATTERN", "DOCKER",
        "Docker Compose for local dev: Define services, networks, volumes. Use depends_on with "
        "healthcheck for startup order. Environment variables from .env file. "
        "Profiles for optional services (debug tools).",
        ["services: app: build: . ports: ['8080:8080'] depends_on: db: condition: service_healthy environment: - DB_URL=jdbc:postgresql://db:5432/mydb",
         "Health: db: image: postgres healthcheck: test: pg_isready interval: 5s",
         "Volumes: db: volumes: [postgres-data:/var/lib/postgresql/data]",
         "Profiles: services: pgadmin: profiles: ['debug']  # docker compose --profile debug up"],
        "HIGH", 0.96, times_applied=80,
        context={"applies_to": ["Docker Compose", "Local development"]}
    ),

    # ── Kubernetes ─────────────────────────────────────────────────────────
    "devops_k8s_deployment": _learning(
        "PATTERN", "KUBERNETES",
        "Kubernetes deployment: Deployment + Service + Ingress. Use resource limits. "
        "Liveness probe for restart, readiness probe for traffic. Use ConfigMap for config, "
        "Secret for credentials. Rolling update strategy for zero-downtime deploys.",
        ["Deployment: replicas: 3, strategy: RollingUpdate (maxSurge: 1, maxUnavailable: 0)",
         "Resources: limits: {cpu: 500m, memory: 512Mi}, requests: {cpu: 250m, memory: 256Mi}",
         "Probes: livenessProbe: httpGet: /actuator/health, readinessProbe: httpGet: /actuator/health/readiness",
         "Secret: kubectl create secret generic db-creds --from-literal=password=xxx"],
        "HIGH", 0.94, times_applied=50,
        context={"applies_to": ["Kubernetes", "GKE", "EKS", "AKS"]}
    ),
    "devops_k8s_services": _learning(
        "PATTERN", "KUBERNETES",
        "K8s Service types: ClusterIP (internal), NodePort (dev), LoadBalancer (cloud), "
        "Ingress (HTTP routing). Use ClusterIP + Ingress for production web apps. "
        "Headless service (clusterIP: None) for StatefulSets.",
        ["ClusterIP: type: ClusterIP, port: 80, targetPort: 8080  # internal only",
         "Ingress: rules: - host: api.supremeai.com, http: paths: - path: /, backend: service: name: api, port: 80",
         "TLS: Cert-manager for auto Let's Encrypt certificates",
         "Headless: for direct pod-to-pod DNS: pod-0.service.namespace.svc.cluster.local"],
        "HIGH", 0.93, times_applied=40,
        context={"applies_to": ["Kubernetes"]}
    ),

    # ── GitHub Actions ─────────────────────────────────────────────────────
    "devops_github_actions": _learning(
        "PATTERN", "CI_CD",
        "GitHub Actions: .github/workflows/*.yml. Triggers: push, pull_request, schedule, workflow_dispatch. "
        "Use composite actions for reuse. Cache dependencies. Matrix builds for multi-version testing. "
        "Use GITHUB_TOKEN for auth. Secrets for credentials.",
        ["Trigger: on: push: branches: [main]; pull_request: branches: [main]",
         "Cache: uses: actions/cache@v4 with: path: ~/.gradle/caches, key: gradle-${{ hashFiles('**/*.gradle*') }}",
         "Matrix: strategy: matrix: java: [17, 21], os: [ubuntu-latest, windows-latest]",
         "Secret: env: DB_PASSWORD: ${{ secrets.DB_PASSWORD }}"],
        "HIGH", 0.96, times_applied=90,
        context={"applies_to": ["GitHub Actions", "CI/CD"]}
    ),
    "devops_ci_pipeline": _learning(
        "PATTERN", "CI_CD",
        "CI pipeline stages: (1) Checkout, (2) Setup runtime, (3) Cache deps, (4) Install deps, "
        "(5) Lint, (6) Test, (7) Build, (8) Security scan, (9) Push image, (10) Deploy. "
        "Fail fast: lint and unit tests before expensive builds.",
        ["Lint first: eslint/checkstyle runs in seconds, catches formatting issues early",
         "Test pyramid: Unit tests (fast, many) → Integration tests (medium) → E2E tests (slow, few)",
         "Build once: Build artifact once, deploy same artifact to staging → production",
         "Notifications: Notify on failure (Slack, email), not on every success"],
        "HIGH", 0.95, times_applied=75,
        context={"applies_to": ["GitHub Actions", "GitLab CI", "Jenkins"]}
    ),

    # ── Cloud Deployment ───────────────────────────────────────────────────
    "devops_cloud_run": _learning(
        "PATTERN", "CLOUD",
        "Google Cloud Run: Serverless containers. Auto-scales to zero. Pay per request. "
        "Deploy from Docker image. Set memory/CPU limits. Use startup probes for JVM warmup. "
        "Environment variables from Secret Manager.",
        ["Deploy: gcloud run deploy api --image gcr.io/PROJECT/api --region us-central1 --memory 512Mi --min-instances 0 --max-instances 10",
         "Env: gcloud run services update api --set-env-vars KEY=VALUE",
         "Secret: gcloud run services update api --set-secrets DB_PASS=db-password:latest",
         "Startup: Set startup CPU boost for JVM apps: --cpu-boost"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["Google Cloud Run", "Docker"], "supremeai": "Primary deployment target"}
    ),
    "devops_firebase_hosting": _learning(
        "PATTERN", "CLOUD",
        "Firebase Hosting: Fast CDN for static sites. Deploy with firebase deploy. "
        "Multiple targets for different sites. Rewrites for SPAs. "
        "Preview channels for PR previews. Connected to Cloud Functions for SSR.",
        ["Deploy: firebase deploy --only hosting:main-dashboard",
         "Target: firebase target:apply hosting main-dashboard supremeai-a",
         "Rewrite: { \"source\": \"**\", \"destination\": \"/index.html\" }  // SPA routing",
         "Preview: firebase hosting:channel:deploy pr-123 --expires 7d"],
        "HIGH", 0.96, times_applied=70,
        context={"applies_to": ["Firebase", "Static sites"], "supremeai": "Admin dashboard hosting"}
    ),

    # ── Monitoring ─────────────────────────────────────────────────────────
    "devops_monitoring": _learning(
        "PATTERN", "MONITORING",
        "Monitoring stack: Prometheus (metrics) + Grafana (dashboards) + AlertManager (alerts). "
        "Four golden signals: Latency, Traffic, Errors, Saturation. "
        "Application metrics: request rate, error rate, duration histogram. Custom business metrics.",
        ["Prometheus: Counter for requests, Histogram for latency, Gauge for active connections",
         "Spring: micrometer-registry-prometheus auto-exposes /actuator/prometheus",
         "Alert: alert: HighErrorRate, expr: rate(http_requests_total{status=~\"5..\"}[5m]) > 0.05",
         "Dashboard: Request rate, P50/P95/P99 latency, error rate, pod CPU/memory"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Prometheus", "Grafana", "Spring Boot"]}
    ),
    "devops_structured_logging": _learning(
        "PATTERN", "MONITORING",
        "Structured logging: JSON format for machine parsing. Include: timestamp, level, service, "
        "requestId, userId, message, error. Use correlation IDs across services. "
        "Centralize with ELK/Loki. Set appropriate log levels per environment.",
        ["Java: log.info(\"Order created\", kv(\"orderId\", id), kv(\"userId\", userId), kv(\"total\", total));",
         "JSON output: {\"timestamp\":\"2026-04-06T10:00:00Z\",\"level\":\"INFO\",\"service\":\"api\",\"orderId\":\"123\",\"message\":\"Order created\"}",
         "Correlation: MDC.put(\"requestId\", UUID.randomUUID().toString()); // propagate in headers",
         "Levels: PROD=INFO, STAGING=DEBUG, DEV=TRACE"],
        "HIGH", 0.95, times_applied=55,
        context={"applies_to": ["ALL"], "tools": ["Logback", "Winston", "structlog"]}
    ),

    # ── Infrastructure as Code ─────────────────────────────────────────────
    "devops_terraform": _learning(
        "PATTERN", "INFRASTRUCTURE",
        "Terraform: Declarative infrastructure. Resources define desired state. Plan before apply. "
        "State stored remotely (GCS, S3). Modules for reuse. Workspaces for environments. "
        "Lock state to prevent concurrent modifications.",
        ["Resource: resource \"google_cloud_run_service\" \"api\" { name = \"api\" location = var.region template { ... } }",
         "State: terraform { backend \"gcs\" { bucket = \"tf-state-supremeai\" prefix = \"prod\" } }",
         "Plan: terraform plan -out=tfplan → terraform apply tfplan",
         "Module: module \"api\" { source = \"./modules/cloud-run\" name = \"api\" image = var.api_image }"],
        "HIGH", 0.93, times_applied=35,
        context={"applies_to": ["Terraform", "GCP", "AWS", "Azure"]}
    ),

    # ── Git Workflow ───────────────────────────────────────────────────────
    "devops_git_workflow": _learning(
        "PATTERN", "GIT",
        "Git workflow: trunk-based development for small teams, GitHub Flow for most projects. "
        "Short-lived feature branches. Conventional commits (feat:, fix:, chore:). "
        "Squash merge to keep main clean. Tag releases with semver.",
        ["Branch: feature/user-auth, fix/login-error, chore/update-deps",
         "Commit: feat(auth): add JWT refresh token rotation",
         "PR: Small PRs (<400 lines). One concern per PR. Include tests.",
         "Release: git tag v1.2.0 → trigger deployment pipeline"],
        "HIGH", 0.96, times_applied=100,
        context={"applies_to": ["Git", "GitHub"]}
    ),
    "devops_git_hooks": _learning(
        "PATTERN", "GIT",
        "Git hooks: pre-commit for lint/format, pre-push for tests. Use Husky (JS) or "
        "pre-commit framework (Python). commitlint for conventional commit messages. "
        "lint-staged to only lint changed files.",
        ["Husky: npx husky add .husky/pre-commit 'npx lint-staged'",
         "lint-staged: { \"*.ts\": [\"eslint --fix\", \"prettier --write\"], \"*.java\": [\"google-java-format\"] }",
         "commitlint: { extends: ['@commitlint/config-conventional'] }",
         "pre-commit: repos: [{repo: url, hooks: [{id: black}, {id: mypy}]}]"],
        "MEDIUM", 0.94, times_applied=50,
        context={"applies_to": ["Git", "JavaScript", "Python"]}
    ),
}

DEVOPS_PATTERNS = {
    "pat_github_actions_java": _pattern(
        "GitHub Actions Java CI", "CI_CD",
        "Complete CI pipeline for Java/Spring Boot with caching, testing, and Docker push",
        "Spring Boot projects with Gradle",
        "name: CI\non: [push, pull_request]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v4\n    - uses: actions/setup-java@v4\n      with: {distribution: temurin, java-version: 21}\n    - uses: gradle/actions/setup-gradle@v3\n    - run: ./gradlew check\n    - run: ./gradlew build -x test\n    - uses: docker/build-push-action@v5\n      if: github.ref == 'refs/heads/main'\n      with: {push: true, tags: 'gcr.io/${{secrets.GCP_PROJECT}}/api:${{github.sha}}'}",
        "GitHub Actions", 0.96, times_used=70
    ),
    "pat_github_actions_node": _pattern(
        "GitHub Actions Node.js CI", "CI_CD",
        "Complete CI pipeline for Node.js/TypeScript with caching and linting",
        "Node.js and React projects",
        "name: CI\non: [push, pull_request]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v4\n    - uses: actions/setup-node@v4\n      with: {node-version: 20, cache: npm}\n    - run: npm ci\n    - run: npm run lint\n    - run: npm run test -- --coverage\n    - run: npm run build",
        "GitHub Actions", 0.96, times_used=75
    ),
    "pat_docker_multistage_java": _pattern(
        "Multi-stage Docker Build (Java)", "DOCKER",
        "Optimized multi-stage Dockerfile for Spring Boot with layer extraction",
        "Production Spring Boot deployments",
        "FROM eclipse-temurin:21-jdk-alpine AS build\nWORKDIR /app\nCOPY gradle/ gradle/\nCOPY gradlew build.gradle.kts settings.gradle.kts ./\nRUN ./gradlew dependencies --no-daemon\nCOPY src/ src/\nRUN ./gradlew bootJar --no-daemon\n\nFROM eclipse-temurin:21-jre-alpine\nRUN addgroup -S app && adduser -S app -G app\nWORKDIR /app\nCOPY --from=build /app/build/libs/*.jar app.jar\nUSER app\nEXPOSE 8080\nHEALTHCHECK --interval=30s CMD wget -qO- http://localhost:8080/actuator/health || exit 1\nENTRYPOINT [\"java\", \"-jar\", \"app.jar\"]",
        "Docker", 0.96, times_used=60
    ),
    "pat_k8s_full_deployment": _pattern(
        "Kubernetes Full Deployment", "KUBERNETES",
        "Complete K8s manifest with Deployment, Service, Ingress, HPA, and ConfigMap",
        "Production Kubernetes deployments",
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: api}\nspec:\n  replicas: 3\n  strategy: {type: RollingUpdate, rollingUpdate: {maxSurge: 1, maxUnavailable: 0}}\n  template:\n    spec:\n      containers:\n      - name: api\n        image: gcr.io/project/api:latest\n        ports: [{containerPort: 8080}]\n        resources: {limits: {cpu: 500m, memory: 512Mi}, requests: {cpu: 250m, memory: 256Mi}}\n        livenessProbe: {httpGet: {path: /actuator/health, port: 8080}, initialDelaySeconds: 30}\n        readinessProbe: {httpGet: {path: /actuator/health/readiness, port: 8080}}\n        envFrom: [{configMapRef: {name: api-config}}, {secretRef: {name: api-secrets}}]",
        "Kubernetes", 0.95, times_used=45
    ),
    "pat_monitoring_config": _pattern(
        "Prometheus + Grafana Monitoring", "MONITORING",
        "Monitoring configuration with Prometheus scrape config, alerting rules, and Grafana dashboard",
        "Production monitoring stack",
        "# prometheus.yml\nscrape_configs:\n- job_name: spring-boot\n  metrics_path: /actuator/prometheus\n  static_configs: [{targets: ['api:8080']}]\n\n# alert.rules.yml\ngroups:\n- name: api\n  rules:\n  - alert: HighErrorRate\n    expr: rate(http_server_requests_seconds_count{status=~\"5..\"}[5m]) / rate(http_server_requests_seconds_count[5m]) > 0.05\n    for: 5m\n    labels: {severity: critical}\n  - alert: HighLatency\n    expr: histogram_quantile(0.95, rate(http_server_requests_seconds_bucket[5m])) > 2\n    for: 5m",
        "Prometheus/Grafana", 0.94, times_used=35
    ),
}

DEVOPS_TEMPLATES = {
    "tpl_docker_compose_full": _code_template(
        "Full Stack Docker Compose", "YAML", "Docker Compose",
        "deployment",
        "version: '3.8'\nservices:\n  api:\n    build: .\n    ports: ['8080:8080']\n    environment:\n      - SPRING_PROFILES_ACTIVE=docker\n      - DB_URL=jdbc:postgresql://db:5432/app\n    depends_on:\n      db: {condition: service_healthy}\n    healthcheck:\n      test: wget -qO- http://localhost:8080/actuator/health\n      interval: 10s\n  db:\n    image: postgres:16-alpine\n    environment:\n      POSTGRES_DB: app\n      POSTGRES_USER: app\n      POSTGRES_PASSWORD: secret\n    volumes: [postgres-data:/var/lib/postgresql/data]\n    healthcheck:\n      test: pg_isready -U app\n      interval: 5s\n  redis:\n    image: redis:7-alpine\n    ports: ['6379:6379']\nvolumes:\n  postgres-data:",
        "Complete Docker Compose with API, PostgreSQL, and Redis for local development",
        ["docker", "compose", "postgres", "redis", "local-dev"]
    ),
    "tpl_github_actions_deploy": _code_template(
        "GitHub Actions Cloud Run Deploy", "YAML", "GitHub Actions",
        "deployment",
        "name: Deploy\non:\n  push: {branches: [main]}\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    permissions: {contents: read, id-token: write}\n    steps:\n    - uses: actions/checkout@v4\n    - uses: google-github-actions/auth@v2\n      with: {workload_identity_provider: ${{secrets.WIF_PROVIDER}}, service_account: ${{secrets.SA_EMAIL}}}\n    - uses: google-github-actions/setup-gcloud@v2\n    - run: gcloud auth configure-docker gcr.io\n    - run: docker build -t gcr.io/${{secrets.GCP_PROJECT}}/api:${{github.sha}} .\n    - run: docker push gcr.io/${{secrets.GCP_PROJECT}}/api:${{github.sha}}\n    - run: gcloud run deploy api --image gcr.io/${{secrets.GCP_PROJECT}}/api:${{github.sha}} --region us-central1",
        "GitHub Actions workflow for building and deploying to Google Cloud Run",
        ["github-actions", "cloud-run", "gcp", "deploy", "ci-cd"]
    ),
    "tpl_nginx_reverse_proxy": _code_template(
        "Nginx Reverse Proxy", "Nginx", "Nginx",
        "configuration",
        "server {\n    listen 80;\n    server_name api.supremeai.com;\n    return 301 https://$host$request_uri;\n}\nserver {\n    listen 443 ssl http2;\n    server_name api.supremeai.com;\n    ssl_certificate /etc/ssl/cert.pem;\n    ssl_certificate_key /etc/ssl/key.pem;\n    location /api/ {\n        proxy_pass http://backend:8080;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n    }\n    location / {\n        root /usr/share/nginx/html;\n        try_files $uri $uri/ /index.html;\n    }\n}",
        "Nginx config with HTTPS redirect, SSL, reverse proxy to backend, and SPA routing",
        ["nginx", "reverse-proxy", "ssl", "production"]
    ),
    "tpl_terraform_cloud_run": _code_template(
        "Terraform Cloud Run", "HCL", "Terraform",
        "infrastructure",
        "resource \"google_cloud_run_v2_service\" \"api\" {\n  name     = \"supremeai-api\"\n  location = var.region\n  template {\n    containers {\n      image = \"gcr.io/${var.project}/api:${var.image_tag}\"\n      ports { container_port = 8080 }\n      resources {\n        limits   = { cpu = \"1000m\", memory = \"512Mi\" }\n        cpu_idle = true\n      }\n      env { name = \"SPRING_PROFILES_ACTIVE\" value = \"production\" }\n      env { name = \"DB_PASSWORD\" value_source { secret_key_ref { secret = google_secret_manager_secret.db_pass.id version = \"latest\" } } }\n    }\n    scaling { min_instance_count = 0 max_instance_count = 10 }\n  }\n}",
        "Terraform config for Google Cloud Run with secrets and auto-scaling",
        ["terraform", "cloud-run", "gcp", "infrastructure"]
    ),
}
