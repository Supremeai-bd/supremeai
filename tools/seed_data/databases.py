"""
Part 7: Database Knowledge
Covers: PostgreSQL, MySQL, MongoDB, Firebase/Firestore, Redis, SQLite, migrations, indexing
~25 learnings + ~15 patterns = 40 documents
"""
from seed_data.helpers import _learning, _pattern

DATABASE_LEARNINGS = {

    # ── PostgreSQL ─────────────────────────────────────────────────────────
    "db_postgres_indexing": _learning(
        "PATTERN", "DATABASE",
        "PostgreSQL indexing: B-tree (default, equality/range), GIN (arrays, JSONB, full-text), "
        "GiST (geometry, ranges), Hash (equality only). Partial indexes for filtered queries. "
        "Composite indexes: leftmost prefix rule. EXPLAIN ANALYZE to verify index usage.",
        ["B-tree: CREATE INDEX idx_users_email ON users(email); -- equality & range queries",
         "Partial: CREATE INDEX idx_active_users ON users(email) WHERE active = true; -- only index active rows",
         "Composite: CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC); -- user_id queries and user_id+date queries both use this",
         "GIN/JSONB: CREATE INDEX idx_metadata ON products USING gin(metadata jsonb_path_ops);"],
        "HIGH", 0.96, times_applied=80,
        context={"applies_to": ["PostgreSQL"], "tool": "EXPLAIN ANALYZE"}
    ),
    "db_postgres_json": _learning(
        "PATTERN", "DATABASE",
        "PostgreSQL JSONB: Store and query JSON natively. JSONB operators: -> (get object), "
        "->> (get text), @> (contains), ? (key exists). GIN index on JSONB columns. "
        "Use for semi-structured data; prefer normal columns for frequently queried fields.",
        ["Column: ALTER TABLE products ADD COLUMN metadata JSONB DEFAULT '{}';",
         "Query: SELECT * FROM products WHERE metadata @> '{\"color\": \"red\"}';",
         "Path: SELECT metadata->>'brand' AS brand FROM products;",
         "Index: CREATE INDEX idx_metadata ON products USING gin(metadata);"],
        "MEDIUM", 0.94, times_applied=45,
        context={"applies_to": ["PostgreSQL 9.4+"]}
    ),
    "db_postgres_performance": _learning(
        "PATTERN", "DATABASE",
        "PostgreSQL performance: Connection pooling (PgBouncer/HikariCP). VACUUM ANALYZE regularly. "
        "Tune shared_buffers (25% RAM), work_mem (per query), effective_cache_size (50-75% RAM). "
        "Use read replicas for heavy read workloads. Partitioning for large tables.",
        ["Connection pool: HikariCP: maximumPoolSize=10, minimumIdle=5, connectionTimeout=30000",
         "VACUUM: Auto-vacuum is on by default; tune autovacuum_vacuum_scale_factor for large tables",
         "Config: shared_buffers = 4GB, work_mem = 64MB, effective_cache_size = 12GB (for 16GB RAM)",
         "Partition: CREATE TABLE orders (id SERIAL, created_at DATE) PARTITION BY RANGE (created_at);"],
        "HIGH", 0.94, times_applied=50,
        context={"applies_to": ["PostgreSQL"]}
    ),
    "db_postgres_migrations": _learning(
        "PATTERN", "DATABASE",
        "Database migrations: Use Flyway (Java) or Alembic (Python). Version-controlled SQL files. "
        "Never modify existing migrations. Backward-compatible changes: add nullable column first, "
        "migrate data, then add constraint. Always have a rollback plan.",
        ["Flyway: V001__create_users.sql, V002__add_email_index.sql — sequential, immutable",
         "Alembic: alembic revision --autogenerate -m 'add user email index'",
         "Safe column add: (1) ALTER TABLE ADD COLUMN nullable, (2) UPDATE data, (3) ALTER SET NOT NULL",
         "Dangerous: Renaming columns, dropping columns — use multi-step migration with deprecation"],
        "HIGH", 0.96, times_applied=70,
        context={"applies_to": ["PostgreSQL", "MySQL", "SQLite"], "tools": ["Flyway", "Alembic", "Liquibase"]}
    ),

    # ── Firebase / Firestore ───────────────────────────────────────────────
    "db_firestore_modeling": _learning(
        "PATTERN", "FIREBASE",
        "Firestore data modeling: Denormalize for read performance. Subcollections for 1:many. "
        "Document size limit 1MB. No joins — duplicate data or use collection groups. "
        "Composite indexes for multi-field queries. Security rules on every collection.",
        ["Subcollection: users/{userId}/orders/{orderId} — query user's orders directly",
         "Denormalize: Store user name in order document — avoid extra read for display",
         "Collection group: db.collectionGroup('orders').where('status', '==', 'pending') — across all users",
         "Index: Composite index auto-suggested by Firestore error messages"],
        "HIGH", 0.96, times_applied=75,
        context={"applies_to": ["Firebase Firestore"], "supremeai": "Primary database"}
    ),
    "db_firestore_security_rules": _learning(
        "PATTERN", "FIREBASE",
        "Firestore security rules: match /databases/{db}/documents { ... }. "
        "Rules: allow read/write: if request.auth != null. Validate data shape. "
        "Check resource.data for existing, request.resource.data for incoming. "
        "Test rules with Firebase emulator.",
        ["Auth: allow read, write: if request.auth != null;",
         "Owner: allow read, update: if request.auth.uid == resource.data.userId;",
         "Admin: allow write: if get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role == 'admin';",
         "Validate: allow create: if request.resource.data.keys().hasAll(['name', 'email']) && request.resource.data.name is string;"],
        "CRITICAL", 0.97, times_applied=80,
        context={"applies_to": ["Firebase Firestore"], "supremeai": "See database.rules.json"}
    ),
    "db_firebase_realtime": _learning(
        "PATTERN", "FIREBASE",
        "Firebase Realtime Database: JSON tree structure. Best for real-time sync (chat, presence). "
        "Rules at each path. Avoid deep nesting — flatten data. Use push() for auto-IDs. "
        "Index with .indexOn for orderByChild queries.",
        ["Read: ref.child('users').child(uid).get()",
         "Listen: ref.child('chat/messages').on('child_added', callback)",
         "Index: { \"messages\": { \".indexOn\": [\"timestamp\", \"userId\"] } }",
         "Flatten: /users/{uid}/profile, /users/{uid}/settings — not deeply nested"],
        "HIGH", 0.95, times_applied=65,
        context={"applies_to": ["Firebase RTDB"], "supremeai": "System learnings stored here"}
    ),

    # ── MongoDB ────────────────────────────────────────────────────────────
    "db_mongodb_modeling": _learning(
        "PATTERN", "DATABASE",
        "MongoDB schema design: Embed for 1:1 and 1:few. Reference for 1:many and many:many. "
        "Design based on access patterns, not normalization. Document size limit 16MB. "
        "Use aggregation pipeline for complex queries. Schema validation for data integrity.",
        ["Embed: { user: { name: 'John', address: { city: 'NYC' } } } — always read together",
         "Reference: { userId: ObjectId('...') } — for large related datasets",
         "Aggregate: db.orders.aggregate([{$match: {status: 'completed'}}, {$group: {_id: '$userId', total: {$sum: '$amount'}}}])",
         "Validation: db.createCollection('users', { validator: { $jsonSchema: { required: ['name', 'email'] } } })"],
        "HIGH", 0.94, times_applied=50,
        context={"applies_to": ["MongoDB"]}
    ),
    "db_mongodb_indexes": _learning(
        "PATTERN", "DATABASE",
        "MongoDB indexes: Single field, compound, multikey (arrays), text, geospatial. "
        "ESR rule for compound indexes: Equality → Sort → Range. "
        "Use explain() to verify index usage. TTL index for auto-expiring documents.",
        ["Compound: db.orders.createIndex({ userId: 1, createdAt: -1 })",
         "Text: db.products.createIndex({ name: 'text', description: 'text' })",
         "TTL: db.sessions.createIndex({ createdAt: 1 }, { expireAfterSeconds: 3600 })",
         "Explain: db.orders.find({userId: '123'}).explain('executionStats')"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["MongoDB"]}
    ),

    # ── Redis ──────────────────────────────────────────────────────────────
    "db_redis_patterns": _learning(
        "PATTERN", "DATABASE",
        "Redis use cases: Cache (GET/SET with TTL), Session store, Rate limiter, "
        "Pub/Sub for real-time messaging, Sorted sets for leaderboards, Streams for event logs. "
        "Set TTL on everything — Redis is not for permanent storage.",
        ["Cache: SET user:123 '{...}' EX 3600  // expire in 1 hour",
         "Rate limit: INCR rate:user:123:minute; EXPIRE rate:user:123:minute 60",
         "Sorted set: ZADD leaderboard 1000 'user123'; ZREVRANGE leaderboard 0 9  // top 10",
         "Pub/Sub: PUBLISH notifications '{userId:123, msg:\"New order\"}'"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["Redis"], "use_cases": ["Caching", "Sessions", "Rate limiting"]}
    ),
    "db_redis_caching_strategy": _learning(
        "PATTERN", "DATABASE",
        "Redis caching strategies: Cache-Aside (lazy load), Write-Through (write to cache + DB), "
        "Write-Behind (write to cache, async to DB). Cache invalidation: TTL, event-based, versioned keys. "
        "Cache stampede protection: lock or probabilistic early expiration.",
        ["Cache-Aside: val = redis.get(key); if(!val) { val = db.query(); redis.setex(key, 3600, val); } return val;",
         "Write-Through: db.save(entity); redis.set(key, entity, 3600);",
         "Invalidation: redis.del('user:' + userId); // on update/delete",
         "Stampede: Use redis lock or add jitter to TTL: ttl = 3600 + random(0, 300)"],
        "HIGH", 0.95, times_applied=55,
        context={"applies_to": ["Redis", "ALL"]}
    ),

    # ── SQLite ─────────────────────────────────────────────────────────────
    "db_sqlite_mobile": _learning(
        "PATTERN", "DATABASE",
        "SQLite for mobile/embedded: Single file database. WAL mode for concurrent reads + one writer. "
        "Use sqflite (Flutter), Room (Android), Core Data (iOS). Batch inserts in transactions. "
        "Don't use for high-write concurrent web servers — use PostgreSQL instead.",
        ["Flutter: final db = await openDatabase('app.db', version: 1, onCreate: (db, v) => db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)'));",
         "WAL mode: PRAGMA journal_mode=WAL; // better concurrent performance",
         "Batch: db.transaction((txn) => txn.rawInsert('INSERT INTO ...')); // 100x faster than individual inserts",
         "Migration: onUpgrade: (db, old, new) { if(old < 2) db.execute('ALTER TABLE users ADD COLUMN email TEXT'); }"],
        "MEDIUM", 0.94, times_applied=40,
        context={"applies_to": ["Flutter", "Android", "iOS", "Electron"]}
    ),

    # ── ORM Best Practices ─────────────────────────────────────────────────
    "db_orm_n_plus_one": _learning(
        "PATTERN", "DATABASE",
        "N+1 query problem: Fetching parent list then querying each child individually. "
        "Fix: JOIN FETCH (JPA), select_related/prefetch_related (Django), include (Prisma), "
        "includes (ActiveRecord). Always check generated SQL in development.",
        ["JPA: @Query(\"SELECT o FROM Order o JOIN FETCH o.items WHERE o.userId = :id\")",
         "Django: Order.objects.select_related('user').prefetch_related('items').all()",
         "Prisma: prisma.order.findMany({ include: { items: true, user: true } })",
         "Detect: Enable SQL logging in dev: spring.jpa.show-sql=true, check for repeated queries"],
        "HIGH", 0.97, times_applied=90,
        context={"applies_to": ["JPA", "Django", "Prisma", "SQLAlchemy"]}
    ),
    "db_orm_transactions": _learning(
        "PATTERN", "DATABASE",
        "Transaction management: ACID properties. Use @Transactional (Spring), atomic() (Django), "
        "prisma.$transaction (Prisma). Read-only transactions for queries. "
        "Avoid long transactions — keep them short. Optimistic locking with version column.",
        ["Spring: @Transactional public void transfer(Long from, Long to, BigDecimal amount) { debit(from, amount); credit(to, amount); }",
         "Read-only: @Transactional(readOnly = true) public List<User> findAll()",
         "Optimistic: @Version private Long version; // JPA auto-checks version on update",
         "Django: with transaction.atomic(): Order.objects.create(...); Payment.objects.create(...)"],
        "HIGH", 0.96, times_applied=75,
        context={"applies_to": ["JPA", "Django", "Prisma", "SQLAlchemy"]}
    ),
}

DATABASE_PATTERNS = {
    "pat_connection_pool": _pattern(
        "Database Connection Pool", "DATABASE",
        "Configure connection pool with proper sizing, timeouts, and health checks",
        "Any application connecting to a relational database",
        "# Spring Boot application.yml\nspring:\n  datasource:\n    hikari:\n      maximum-pool-size: 10\n      minimum-idle: 5\n      connection-timeout: 30000\n      idle-timeout: 600000\n      max-lifetime: 1800000\n      pool-name: SupremeAI-Pool\n      connection-test-query: SELECT 1",
        "Spring Boot/HikariCP", 0.96, times_used=70
    ),
    "pat_repository_firebase": _pattern(
        "Firebase Repository", "FIREBASE",
        "Repository pattern over Firestore with CRUD, queries, and error handling",
        "Data access layer for Firebase Firestore",
        "class UserRepository { private final Firestore db; private static final String COLLECTION = \"users\"; public CompletableFuture<User> findById(String id) { return db.collection(COLLECTION).document(id).get().thenApply(doc -> doc.exists() ? doc.toObject(User.class) : null); } public CompletableFuture<List<User>> findActive() { return db.collection(COLLECTION).whereEqualTo(\"active\", true).orderBy(\"createdAt\", Direction.DESCENDING).limit(100).get().thenApply(qs -> qs.toObjects(User.class)); } public CompletableFuture<String> save(User user) { DocumentReference ref = db.collection(COLLECTION).document(); user.setId(ref.getId()); return ref.set(user).thenApply(wr -> ref.getId()); } }",
        "Java/Firestore", 0.95, times_used=55
    ),
    "pat_migration_flyway": _pattern(
        "Flyway Migration Setup", "DATABASE",
        "Flyway migration configuration with versioned SQL scripts",
        "Database schema management in Spring Boot",
        "-- V001__create_users.sql\nCREATE TABLE users (\n  id BIGSERIAL PRIMARY KEY,\n  username VARCHAR(50) NOT NULL UNIQUE,\n  email VARCHAR(255) NOT NULL UNIQUE,\n  password_hash VARCHAR(255) NOT NULL,\n  role VARCHAR(20) DEFAULT 'USER',\n  active BOOLEAN DEFAULT true,\n  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n);\nCREATE INDEX idx_users_email ON users(email);\nCREATE INDEX idx_users_active ON users(active) WHERE active = true;",
        "Flyway/PostgreSQL", 0.96, times_used=65
    ),
    "pat_redis_cache_service": _pattern(
        "Redis Cache Service", "DATABASE",
        "Cache service with cache-aside pattern, TTL, and invalidation",
        "Caching layer in any application",
        "@Service class CacheService { @Autowired RedisTemplate<String, Object> redis; public <T> T getOrLoad(String key, Duration ttl, Supplier<T> loader) { T cached = (T) redis.opsForValue().get(key); if (cached != null) return cached; T value = loader.get(); redis.opsForValue().set(key, value, ttl); return value; } public void invalidate(String... keys) { redis.delete(Arrays.asList(keys)); } public void invalidatePattern(String pattern) { Set<String> keys = redis.keys(pattern); if (keys != null && !keys.isEmpty()) redis.delete(keys); } }",
        "Spring Boot/Redis", 0.95, times_used=50
    ),
    "pat_soft_delete": _pattern(
        "Soft Delete Pattern", "DATABASE",
        "Mark records as deleted instead of physically removing them",
        "When you need to retain data for auditing or recovery",
        "// Entity\n@Entity @Where(clause = \"deleted = false\") class User { @Column Long id; @Column boolean deleted = false; @Column Instant deletedAt; }\n\n// Repository\ninterface UserRepository extends JpaRepository<User, Long> { @Query(\"SELECT u FROM User u WHERE u.id = :id\") Optional<User> findByIdIncludeDeleted(@Param(\"id\") Long id); @Modifying @Query(\"UPDATE User u SET u.deleted = true, u.deletedAt = :now WHERE u.id = :id\") void softDelete(@Param(\"id\") Long id, @Param(\"now\") Instant now); }",
        "JPA/Hibernate", 0.94, times_used=45
    ),
}
