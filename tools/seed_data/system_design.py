"""
System Design Knowledge Base
~30 learnings + ~8 patterns organized by category
"""
from seed_data.helpers import _learning, _pattern

# ============================================================================
# DISTRIBUTED SYSTEMS
# ============================================================================

DISTRIBUTED_SYSTEMS_LEARNINGS = {
    "sd_cap_theorem": _learning(
        "PATTERN", "SYSTEM_DESIGN",
        "CAP theorem: Distributed system can guarantee at most 2 of 3: Consistency, Availability, "
        "Partition tolerance. CP (consistent but may reject requests): Zookeeper, etcd. "
        "AP (available but eventually consistent): Cassandra, DynamoDB. Partition tolerance is non-negotiable.",
        ["CP systems: Strong consistency, may return errors during partition — banking, inventory",
         "AP systems: Always available, eventual consistency — social media feeds, caching",
         "PACELC: Extension — during Partition choose A or C; Else choose Latency or Consistency",
         "Real-world: Most systems choose AP with eventual consistency and conflict resolution"],
        "HIGH", 0.96, times_applied=55,
        context={"applies_to": ["ALL"], "domain": "distributed systems"}
    ),
    "sd_load_balancing": _learning(
        "PATTERN", "SYSTEM_DESIGN",
        "Load balancing strategies: Round-robin (simple), least connections (best for varying request times), "
        "weighted (different server capacities), IP hash (session affinity). "
        "L4 (TCP) vs L7 (HTTP) load balancers. Health checks to remove unhealthy instances.",
        ["Nginx: upstream backend { least_conn; server app1:8080; server app2:8080; }",
         "K8s: Service type LoadBalancer or Ingress controller",
         "Cloud: GCP Cloud Load Balancing, AWS ALB/NLB, Azure Application Gateway",
         "Health check: GET /health every 10s, 3 failures → remove from pool, 2 successes → re-add"],
        "HIGH", 0.96, times_applied=65,
        context={"applies_to": ["ALL"]}
    ),
    "sd_horizontal_scaling": _learning(
        "PATTERN", "SYSTEM_DESIGN",
        "Horizontal vs vertical scaling: Horizontal (add more machines) preferred — no single point of failure, "
        "linear cost scaling. Vertical (bigger machine) simpler but has limits. "
        "Stateless services scale horizontally. Store state externally (Redis, DB). Auto-scale on metrics.",
        ["Stateless: No in-memory sessions — use Redis/JWT for auth state",
         "Auto-scale: K8s HPA (CPU > 70% → add pod), Cloud Run (request concurrency)",
         "Database scaling: Read replicas, sharding, connection pooling",
         "Rule: If you can't add a second instance and have it work, it's not horizontally scalable"],
        "HIGH", 0.96, times_applied=60,
        context={"applies_to": ["ALL"]}
    ),
    "sd_database_sharding": _learning(
        "PATTERN", "SYSTEM_DESIGN",
        "Database sharding: Split data across multiple databases by shard key. "
        "Range-based (date ranges), hash-based (user_id % N), directory-based (lookup table). "
        "Challenges: Cross-shard queries, rebalancing, joins. Use only when single DB can't handle load.",
        ["Hash shard: shard = hash(user_id) % num_shards — even distribution",
         "Range shard: 2024 data → shard_1, 2025 data → shard_2 — easy archive",
         "Avoid: Cross-shard joins, cross-shard transactions — redesign schema instead",
         "Alternative: Read replicas + connection pooling before sharding, it is simpler"],
        "MEDIUM", 0.94, times_applied=30,
        context={"applies_to": ["PostgreSQL", "MySQL", "MongoDB"]}
    ),
}

# ============================================================================
# CLOUD PLATFORMS
# ============================================================================

CLOUD_LEARNINGS = {
    "sd_aws_core": _learning(
        "PATTERN", "CLOUD",
        "AWS core services: EC2 (VMs), Lambda (serverless), S3 (object storage), "
        "RDS (managed SQL), DynamoDB (managed NoSQL), SQS (queue), SNS (pub/sub), "
        "ECS/EKS (containers), CloudFront (CDN), Route 53 (DNS), IAM (auth).",
        ["Compute: Lambda for event-driven, ECS/Fargate for containers, EC2 for full control",
         "Storage: S3 for files (11 nines durability), EBS for block storage",
         "Database: RDS for SQL, DynamoDB for NoSQL key-value",
         "Queue: SQS for point-to-point, SNS for fan-out pub/sub"],
        "HIGH", 0.95, times_applied=80,
        context={"applies_to": ["ALL"], "provider": "AWS"}
    ),
    "sd_gcp_core": _learning(
        "PATTERN", "CLOUD",
        "GCP core services: Compute Engine, Cloud Run, Cloud Functions, GKE, Cloud SQL, Firestore, "
        "Cloud Storage, Pub/Sub, Cloud CDN, Cloud Load Balancing, IAM, Secret Manager.",
        ["Serverless: Cloud Run for containers (scale to zero), Cloud Functions for events",
         "Database: Cloud SQL, Firestore, Bigtable, Spanner",
         "Messaging: Pub/Sub for async messaging"],
        "HIGH", 0.96, times_applied=90,
        context={"applies_to": ["ALL"], "provider": "GCP"}
    ),
}

# ============================================================================
# RESILIENCE PATTERNS
# ============================================================================

RESILIENCE_LEARNINGS = {
    "sd_caching_strategy": _learning(
        "PATTERN", "SYSTEM_DESIGN",
        "Caching strategies: Cache-aside (app manages), Write-through, Write-behind, Read-through. "
        "Invalidation: TTL, event-based, versioned keys.",
        ["Cache-aside: if cache miss → load from DB → store in cache with TTL",
         "TTL: 5min hot data, 1hr config, 24hr static",
         "Stampede prevention: distributed locks or probabilistic early expiration"],
        "HIGH", 0.96, times_applied=70,
        context={"applies_to": ["Redis", "ALL"]}
    ),
    "sd_circuit_breaker": _learning(
        "PATTERN", "SYSTEM_DESIGN",
        "Circuit breaker: CLOSED → OPEN (fail fast) → HALF-OPEN (test recovery). "
        "Libraries: Resilience4j, Polly, Opossum.",
        ["Resilience4j: @CircuitBreaker(name='svc', fallbackMethod='fallback')",
         "Config: failureRateThreshold=50, waitDurationInOpenState=30s"],
        "HIGH", 0.95, times_applied=45,
        context={"applies_to": ["Java", "Node.js", ".NET"]}
    ),
}

# ============================================================================
# MESSAGING
# ============================================================================

MESSAGING_LEARNINGS = {
    "sd_kafka": _learning(
        "PATTERN", "MESSAGING",
        "Apache Kafka: Topics → Partitions → Consumer Groups. "
        "High throughput, durable log, ordered within partition. "
        "Use for: Event sourcing, log aggregation, stream processing.",
        ["Producer: producer.send(new ProducerRecord<>('topic', key, value));",
         "Partitioning: Same key → same partition → ordered per entity",
         "Retention: Keep days/weeks — replay from any offset"],
        "HIGH", 0.95, times_applied=50,
        context={"applies_to": ["Java", "Python"]}
    ),
}

# ============================================================================
# OBSERVABILITY
# ============================================================================

OBSERVABILITY_LEARNINGS = {
    "sd_three_pillars": _learning(
        "PATTERN", "OBSERVABILITY",
        "Three pillars: (1) Logs — structured JSON, correlation IDs. "
        "(2) Metrics — Prometheus counters/gauges/histograms. "
        "(3) Traces — OpenTelemetry distributed tracing.",
        ["Logs: { level, message, traceId, service }",
         "Metrics: http_requests_total{method, status}",
         "Traces: W3C TraceContext propagation"],
        "HIGH", 0.96, times_applied=60,
        context={"applies_to": ["ALL"]}
    ),
}

# ============================================================================
# PATTERNS
# ============================================================================

SYSTEM_DESIGN_PATTERNS = {
    "pat_service_discovery": _pattern(
        "Service Discovery", "SYSTEM_DESIGN",
        "Dynamic service discovery for microservices",
        "Microservices with dynamic scaling",
        "// K8s DNS: http://user-service.default.svc.cluster.local:8080\n// Spring Cloud: @EnableDiscoveryClient",
        "Spring Cloud / K8s", 0.94, times_used=40
    ),
    "pat_saga_orchestration": _pattern(
        "Saga Orchestrator", "SYSTEM_DESIGN",
        "Distributed transactions with compensating actions",
        "Multi-service operations (order → payment → inventory)",
        "@Service class OrderSagaOrchestrator { try { create → charge → ship; } catch { compensate; } }",
        "Java / Spring Boot", 0.95, times_used=30
    ),
    "pat_bulkhead": _pattern(
        "Bulkhead", "SYSTEM_DESIGN",
        "Isolate failures — limit concurrent calls per dependency",
        "Microservices calling external services",
        "@Bulkhead(name='svc', type=THREADPOOL) CompletableFuture<User> getUser(Long id) { ... }",
        "Spring Boot + Resilience4j", 0.94, times_used=25
    ),
    "pat_cqrs": _pattern(
        "CQRS", "SYSTEM_DESIGN",
        "Separate read/write models for complex queries",
        "High-read systems (dashboards, analytics)",
        "Write: Order entity; Read: OrderView projection updated via events",
        "Spring Boot", 0.95, times_used=30
    ),
}

# Combined exports for backward compatibility
SYSTEM_DESIGN_LEARNINGS = {
    **DISTRIBUTED_SYSTEMS_LEARNINGS,
    **CLOUD_LEARNINGS,
    **RESILIENCE_LEARNINGS,
    **MESSAGING_LEARNINGS,
    **OBSERVABILITY_LEARNINGS,
}