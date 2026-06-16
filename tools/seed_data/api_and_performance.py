"""
Part 10: API Design & Performance Knowledge
Covers: REST API design, GraphQL, gRPC, WebSocket, caching, optimization, profiling
~30 learnings + ~15 patterns = 45 documents
"""
from seed_data.helpers import _learning, _pattern

API_LEARNINGS = {

    # ── REST API Design ────────────────────────────────────────────────────
    "api_rest_conventions": _learning(
        "PATTERN", "API_DESIGN",
        "REST API conventions: Nouns for resources (POST /users, not POST /createUser). "
        "HTTP methods: GET (read), POST (create), PUT (full update), PATCH (partial update), DELETE (remove). "
        "Plural nouns: /users, /orders. Nested resources: /users/{id}/orders. API versioning: /api/v1/.",
        ["GET /api/v1/users → list users (200)",
         "POST /api/v1/users → create user (201, Location header)",
         "GET /api/v1/users/{id} → get user (200, 404)",
         "PATCH /api/v1/users/{id} → partial update (200, 404)",
         "DELETE /api/v1/users/{id} → delete (204, 404)"],
        "HIGH", 0.97, times_applied=150,
        context={"applies_to": ["ALL"], "standard": "REST"}
    ),
    "api_rest_responses": _learning(
        "PATTERN", "API_DESIGN",
        "API response format: Consistent envelope or flat response. Status codes: 200 OK, 201 Created, "
        "204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, "
        "409 Conflict, 422 Unprocessable, 429 Too Many Requests, 500 Internal Error.",
        ["Success: { 'data': {...}, 'meta': { 'page': 1, 'total': 100 } }",
         "Error: { 'error': { 'code': 'VALIDATION_ERROR', 'message': 'Email is required', 'details': [...] } }",
         "Created: 201 + Location: /api/v1/users/123 header",
         "Problem Details (RFC 7807): { 'type': '/errors/validation', 'title': 'Validation Failed', 'status': 400, 'detail': '...' }"],
        "HIGH", 0.96, times_applied=120,
        context={"applies_to": ["ALL"], "standard": "RFC 7807 Problem Details"}
    ),
    "api_pagination": _learning(
        "PATTERN", "API_DESIGN",
        "API pagination: Offset-based (page + size) or cursor-based (after token). "
        "Cursor-based for real-time data and large datasets. Include pagination metadata. "
        "Default to reasonable page size (20-50). Maximum page size cap (100).",
        ["Offset: GET /users?page=2&size=20 → { 'data': [...], 'meta': { 'page': 2, 'size': 20, 'total': 150, 'totalPages': 8 } }",
         "Cursor: GET /users?after=eyJpZCI6MTAwfQ&limit=20 → { 'data': [...], 'cursors': { 'after': 'eyJpZCI6MTIwfQ', 'hasMore': true } }",
         "Spring: Pageable pageable; Page<User> page = repo.findAll(pageable);",
         "When to use cursor: Infinite scroll, real-time feeds, large datasets (>10K records)"],
        "HIGH", 0.95, times_applied=80,
        context={"applies_to": ["ALL"]}
    ),
    "api_filtering_sorting": _learning(
        "PATTERN", "API_DESIGN",
        "API filtering and sorting: Use query parameters for filtering. Support multiple filters. "
        "Sorting: sort=field:asc|desc. Field selection: fields=name,email. "
        "Search: q=searchterm for full-text search.",
        ["Filter: GET /users?status=active&role=admin&created_after=2026-01-01",
         "Sort: GET /users?sort=created_at:desc,name:asc",
         "Fields: GET /users?fields=id,name,email (sparse fieldsets)",
         "Search: GET /users?q=john — full-text search across name, email"],
        "MEDIUM", 0.94, times_applied=60,
        context={"applies_to": ["ALL"]}
    ),
    "api_versioning": _learning(
        "PATTERN", "API_DESIGN",
        "API versioning strategies: URL path (/api/v1/users) — most common and clearest. "
        "Header (Accept: application/vnd.api+json;version=1) — cleaner URLs. "
        "Query param (?version=1) — easy but not RESTful. Prefer URL path versioning.",
        ["URL path: /api/v1/users → /api/v2/users (breaking changes)",
         "When to version: Remove field, change field type, change response structure",
         "When NOT to version: Adding new optional fields, adding new endpoints",
         "Deprecation: Add Sunset header, document migration path, support old version for N months"],
        "MEDIUM", 0.94, times_applied=45,
        context={"applies_to": ["ALL"]}
    ),
    "api_authentication": _learning(
        "PATTERN", "API_DESIGN",
        "API authentication methods: Bearer token (JWT) for user auth. API key for service auth. "
        "OAuth2 for third-party access. Use Authorization header. Never send credentials in URL. "
        "Rate limit auth endpoints more strictly.",
        ["Bearer: Authorization: Bearer eyJhbGciOi...",
         "API Key: X-API-Key: sk_live_... (for service-to-service)",
         "OAuth2: Authorization Code flow for user auth, Client Credentials for service auth",
         "Refresh: Short-lived access token (15min) + long-lived refresh token (7 days)"],
        "CRITICAL", 0.97, times_applied=100,
        context={"applies_to": ["ALL"]}
    ),
    "api_idempotency": _learning(
        "PATTERN", "API_DESIGN",
        "API idempotency: GET, PUT, DELETE are idempotent by nature. POST is not. "
        "For POST: use Idempotency-Key header. Store key → response mapping. "
        "Return cached response for duplicate requests. Critical for payment and order APIs.",
        ["Header: Idempotency-Key: unique-request-uuid-123",
         "Server: if (cache.has(key)) return cache.get(key); result = processRequest(); cache.set(key, result, ttl=24h);",
         "PUT: Replace entire resource — always idempotent by design",
         "Use case: Payment processing, order creation, any non-retriable side effect"],
        "HIGH", 0.94, times_applied=40,
        context={"applies_to": ["ALL"], "critical_for": ["Payments", "Orders"]}
    ),

    # ── GraphQL ────────────────────────────────────────────────────────────
    "api_graphql_basics": _learning(
        "PATTERN", "API_DESIGN",
        "GraphQL: Single endpoint, client specifies data shape. Query for reads, Mutation for writes, "
        "Subscription for real-time. Resolvers per field. DataLoader for N+1 prevention. "
        "Use when: Multiple clients need different data shapes.",
        ["Query: query { user(id: \"1\") { name email orders { id total } } }",
         "Mutation: mutation { createUser(input: { name: \"John\" }) { id name } }",
         "DataLoader: Batch and cache database lookups per request to avoid N+1",
         "When to use: Mobile + Web clients needing different response shapes from same API"],
        "MEDIUM", 0.93, times_applied=35,
        context={"applies_to": ["TypeScript", "Java", "Python"]}
    ),

    # ── WebSocket ──────────────────────────────────────────────────────────
    "api_websocket": _learning(
        "PATTERN", "API_DESIGN",
        "WebSocket: Full-duplex persistent connection. Use for: real-time chat, live updates, "
        "collaborative editing, game state. Use Socket.IO for ease, raw WS for performance. "
        "Implement heartbeat/ping-pong for connection health. Handle reconnection client-side.",
        ["Server: @ServerEndpoint(\"/ws/chat\") class ChatEndpoint { @OnMessage void onMessage(String msg, Session session) { broadcast(msg); } }",
         "Socket.IO: io.on('connection', (socket) => { socket.on('message', (data) => io.emit('message', data)); });",
         "Client: const ws = new WebSocket(url); ws.onmessage = (e) => handleMessage(JSON.parse(e.data));",
         "Reconnect: Use exponential backoff: 1s, 2s, 4s, 8s, max 30s"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Java", "Node.js", "Python"]}
    ),
}

API_PATTERNS = {
    "pat_rest_controller_template": _pattern(
        "REST Controller Template", "API_DESIGN",
        "Complete REST controller with CRUD, pagination, filtering, and proper HTTP semantics",
        "Any REST API endpoint",
        "@RestController @RequestMapping(\"/api/v1/products\")\npublic class ProductController {\n  @GetMapping\n  public Page<ProductDTO> list(@RequestParam(required=false) String category, Pageable pageable) { return service.findAll(category, pageable); }\n  @GetMapping(\"/{id}\")\n  public ProductDTO get(@PathVariable Long id) { return service.findById(id).orElseThrow(() -> new ResponseStatusException(NOT_FOUND)); }\n  @PostMapping @ResponseStatus(CREATED)\n  public ProductDTO create(@Valid @RequestBody CreateProductDTO dto) { return service.create(dto); }\n  @PatchMapping(\"/{id}\")\n  public ProductDTO update(@PathVariable Long id, @Valid @RequestBody UpdateProductDTO dto) { return service.update(id, dto); }\n  @DeleteMapping(\"/{id}\") @ResponseStatus(NO_CONTENT)\n  public void delete(@PathVariable Long id) { service.delete(id); }\n}",
        "Spring Boot", 0.97, times_used=110
    ),
    "pat_api_error_response": _pattern(
        "API Error Response (RFC 7807)", "API_DESIGN",
        "Standardized error response format using Problem Details RFC 7807",
        "Global error handling in REST APIs",
        "// Spring Boot 3+ auto-supports ProblemDetail\n@ControllerAdvice\npublic class ApiExceptionHandler {\n  @ExceptionHandler(EntityNotFoundException.class)\n  ProblemDetail notFound(EntityNotFoundException e) {\n    var pd = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());\n    pd.setType(URI.create(\"/errors/not-found\"));\n    pd.setTitle(\"Resource Not Found\");\n    return pd;\n  }\n  @ExceptionHandler(MethodArgumentNotValidException.class)\n  ProblemDetail validation(MethodArgumentNotValidException e) {\n    var pd = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST);\n    pd.setTitle(\"Validation Error\");\n    pd.setProperty(\"violations\", e.getFieldErrors().stream().map(f -> Map.of(\"field\",f.getField(),\"message\",f.getDefaultMessage())).toList());\n    return pd;\n  }\n}",
        "Spring Boot 3+", 0.96, times_used=80
    ),
    "pat_api_dto_mapping": _pattern(
        "DTO Mapping Pattern", "API_DESIGN",
        "Map between domain entities and DTOs using records and a mapper",
        "Controller/Service boundary in REST APIs",
        "// DTOs (records)\nrecord UserDTO(Long id, String name, String email, Instant createdAt) {}\nrecord CreateUserDTO(@NotBlank String name, @Email String email, @Size(min=8) String password) {}\n// Mapper\n@Component class UserMapper {\n  UserDTO toDTO(User u) { return new UserDTO(u.getId(), u.getName(), u.getEmail(), u.getCreatedAt()); }\n  User toEntity(CreateUserDTO dto) { User u = new User(); u.setName(dto.name()); u.setEmail(dto.email()); return u; }\n  Page<UserDTO> toDTOPage(Page<User> page) { return page.map(this::toDTO); }\n}",
        "Java", 0.96, times_used=90
    ),
    "pat_rate_limiter": _pattern(
        "API Rate Limiter", "API_DESIGN",
        "Token bucket rate limiter with per-user and global limits",
        "API gateways and middleware",
        "// Spring Boot with Bucket4j\n@Component class RateLimitFilter extends OncePerRequestFilter {\n  private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();\n  private Bucket resolveBucket(String key) {\n    return buckets.computeIfAbsent(key, k -> Bucket.builder()\n      .addLimit(Bandwidth.classic(100, Refill.intervally(100, Duration.ofMinutes(1))))\n      .build());\n  }\n  @Override protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) {\n    String key = req.getRemoteAddr();\n    Bucket bucket = resolveBucket(key);\n    if (bucket.tryConsume(1)) { chain.doFilter(req, res); }\n    else { res.setStatus(429); res.setHeader(\"Retry-After\", \"60\"); res.getWriter().write(\"{\\\"error\\\":\\\"Too many requests\\\"}\"); }\n  }\n}",
        "Spring Boot", 0.94, times_used=45
    ),
    "pat_api_health_check": _pattern(
        "Health Check Endpoint", "API_DESIGN",
        "Comprehensive health check that verifies all dependencies",
        "Production APIs with monitoring",
        "@RestController @RequestMapping(\"/health\")\npublic class HealthController {\n  @Autowired DataSource ds;\n  @Autowired RedisTemplate<String,String> redis;\n\n  @GetMapping\n  public Map<String,Object> health() {\n    Map<String,Object> status = new LinkedHashMap<>();\n    status.put(\"status\", \"UP\");\n    status.put(\"timestamp\", Instant.now());\n    status.put(\"db\", checkDb());\n    status.put(\"redis\", checkRedis());\n    status.put(\"memory\", Runtime.getRuntime().freeMemory() / 1024 / 1024 + \"MB free\");\n    if (status.values().stream().anyMatch(v -> \"DOWN\".equals(v))) status.put(\"status\", \"DEGRADED\");\n    return status;\n  }\n  private String checkDb() { try { ds.getConnection().isValid(2); return \"UP\"; } catch (Exception e) { return \"DOWN\"; } }\n  private String checkRedis() { try { redis.opsForValue().get(\"health\"); return \"UP\"; } catch (Exception e) { return \"DOWN\"; } }\n}",
        "Spring Boot", 0.95, times_used=60
    ),
}

PERFORMANCE_LEARNINGS = {

    # ── Application Performance ────────────────────────────────────────────
    "perf_caching_layers": _learning(
        "PATTERN", "PERFORMANCE",
        "Caching layers: (1) Browser cache (Cache-Control headers), (2) CDN cache (CloudFlare, Fastly), "
        "(3) Application cache (Redis), (4) Database query cache. Cache at the highest layer possible. "
        "Invalidation strategies: TTL, event-based, versioned URLs.",
        ["Browser: Cache-Control: public, max-age=3600 for static assets",
         "CDN: Cache static assets at edge. Purge on deploy.",
         "Redis: Cache DB query results with TTL. Invalidate on write.",
         "DB: Connection pool + prepared statement cache. Query plan cache."],
        "HIGH", 0.96, times_applied=80,
        context={"applies_to": ["ALL"]}
    ),
    "perf_database_optimization": _learning(
        "PATTERN", "PERFORMANCE",
        "Database optimization: Use indexes (B-tree for equality/range, GIN for JSONB/arrays). "
        "EXPLAIN ANALYZE every slow query. Avoid N+1 queries. Use connection pooling. "
        "Denormalize for read-heavy workloads. Partition large tables.",
        ["Index: Add indexes on WHERE, JOIN, ORDER BY columns. Drop unused indexes.",
         "N+1: Use JOIN FETCH, prefetch_related, or DataLoader",
         "Connection pool: HikariCP max 10 connections per service instance",
         "Monitor: pg_stat_statements for slow query identification"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["PostgreSQL", "MySQL", "ALL"]}
    ),
    "perf_async_processing": _learning(
        "PATTERN", "PERFORMANCE",
        "Async processing: Move slow operations out of request path. Use message queues (RabbitMQ, "
        "SQS, Pub/Sub) for background jobs. Event-driven for email, notifications, analytics. "
        "Return 202 Accepted for long-running tasks, provide status endpoint.",
        ["Queue: Send email asynchronously — don't block API response",
         "Pattern: POST /orders → 202 Accepted + poll GET /orders/{id}/status",
         "Spring: @Async + ThreadPoolTaskExecutor for simple cases",
         "Queues: RabbitMQ, Google Pub/Sub, AWS SQS for distributed systems"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["ALL"]}
    ),
    "perf_frontend_optimization": _learning(
        "PATTERN", "PERFORMANCE",
        "Frontend performance: Bundle splitting (lazy routes). Image optimization (WebP, lazy loading). "
        "Minimize re-renders (React.memo, useMemo). Virtual lists for large datasets. "
        "Debounce search inputs. Compress assets (gzip/brotli).",
        ["Code split: React.lazy(() => import('./HeavyComponent'))",
         "Images: <img loading='lazy' srcSet='img-400.webp 400w, img-800.webp 800w' />",
         "Debounce: const debouncedSearch = useMemo(() => debounce(search, 300), [])",
         "Virtual list: react-window for rendering 10K+ items efficiently"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["React", "Next.js", "Web"]}
    ),
    "perf_jvm_tuning": _learning(
        "PATTERN", "PERFORMANCE",
        "JVM tuning: -Xms (initial heap) = -Xmx (max heap) for production. G1GC default is good. "
        "Container-aware: -XX:+UseContainerSupport -XX:MaxRAMPercentage=75. "
        "Profile with JFR (Java Flight Recorder) and VisualVM. Enable GC logging for production.",
        ["Container: java -XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -jar app.jar",
         "GC log: -Xlog:gc*:file=gc.log:time,uptime:filecount=5,filesize=10m",
         "Profile: -XX:StartFlightRecording=duration=60s,filename=recording.jfr",
         "Spring Boot: Enable virtual threads for IO-bound apps: spring.threads.virtual.enabled=true"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Java", "Spring Boot"]}
    ),
    "perf_connection_pooling": _learning(
        "PATTERN", "PERFORMANCE",
        "Connection pooling: Reuse database connections instead of creating new ones per request. "
        "HikariCP for Java (default in Spring Boot). Pool size = (core_count * 2) + disk_spindles. "
        "Monitor active/idle/waiting connections. Set connection timeout and max lifetime.",
        ["HikariCP: maximumPoolSize=10, minimumIdle=5, connectionTimeout=30000, maxLifetime=1800000",
         "Formula: connections ≈ (2 * CPU cores) + effective_spindle_count",
         "Monitor: HikariCP exposes JMX metrics — track active, idle, pending",
         "Warning: Too many connections slow down the DB. 10 per service instance is usually enough."],
        "HIGH", 0.96, times_applied=65,
        context={"applies_to": ["Java", "Python", "Node.js"]}
    ),
    "perf_lazy_loading": _learning(
        "PATTERN", "PERFORMANCE",
        "Lazy loading: Load resources only when needed. Frontend: Code splitting, image lazy loading, "
        "infinite scroll. Backend: Lazy entity relations (JPA), pagination, cursor-based fetching. "
        "Don't eager-load everything — load on demand.",
        ["React: const Component = React.lazy(() => import('./Component')); <Suspense fallback={<Loading />}><Component /></Suspense>",
         "Images: loading='lazy' attribute on img tags",
         "JPA: @ManyToOne(fetch = FetchType.LAZY) — default for collections",
         "API: Return summary in list, full details on single-resource GET"],
        "HIGH", 0.95, times_applied=75,
        context={"applies_to": ["ALL"]}
    ),
    "perf_compression": _learning(
        "PATTERN", "PERFORMANCE",
        "Response compression: Gzip or Brotli for text responses. 60-80% size reduction for JSON/HTML. "
        "Spring: server.compression.enabled=true. Express: compression() middleware. "
        "Nginx: gzip on. Don't compress already compressed formats (images, videos).",
        ["Spring: server.compression.enabled=true, server.compression.min-response-size=1024",
         "Express: app.use(compression())",
         "Nginx: gzip on; gzip_types text/plain application/json application/javascript;",
         "Brotli: 15-20% better than gzip. Supported by all modern browsers."],
        "MEDIUM", 0.95, times_applied=55,
        context={"applies_to": ["ALL"]}
    ),
}
