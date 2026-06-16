"""
Design Patterns Knowledge Base
GoF patterns, architectural patterns, microservices
~30 learnings + ~25 patterns organized by category
"""
from seed_data.helpers import _learning, _pattern

# ============================================================================
# CREATIONAL PATTERNS
# ============================================================================

CREATIONAL_PATTERNS = {
    "dp_singleton": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Singleton: One global instance. Java: enum or static holder. Spring: @Component singletons. "
        "Avoid mutable state in multi-threaded contexts.",
        ["Java enum: enum Config { INSTANCE; }",
         "Spring: @Service classes are singletons by default",
         "Anti-pattern: Global mutable state — prefer DI"],
        "MEDIUM", 0.95, times_applied=60,
        context={"applies_to": ["Java", "Python", "TypeScript"], "gof": "Creational"}
    ),
    "dp_factory": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Factory Method: Create objects without specifying concrete class. "
        "Use when constructor logic is complex or type depends on input.",
        ["Switch-based factory for Notification types",
         "Spring @Bean methods are factories",
         "Abstract factory for UI themes"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["Java", "Python", "TypeScript"], "gof": "Creational"}
    ),
    "dp_builder": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Builder: Step-by-step construction for 4+ parameters. Fluent API.",
        ["Lombok @Builder for Java",
         "Kotlin: default parameters reduce need for explicit builders"],
        "MEDIUM", 0.96, times_applied=80,
        context={"applies_to": ["Java", "TypeScript", "Python"], "gof": "Creational"}
    ),
}

# ============================================================================
# STRUCTURAL PATTERNS
# ============================================================================

STRUCTURAL_PATTERNS = {
    "dp_adapter": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Adapter: Convert one interface to another. Use for third-party integrations.",
        ["PayPalAdapter implements PaymentGateway",
         "FirebaseAuthAdapter implements AuthProvider",
         "Wrap different AI provider APIs behind common interface"],
        "HIGH", 0.94, times_applied=55,
        context={"applies_to": ["Java", "TypeScript", "Python"], "gof": "Structural"}
    ),
    "dp_decorator": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Decorator: Add behavior dynamically. Use for logging, caching, retry, auth.",
        ["Java: LoggingService wraps UserService",
         "Python: @retry decorator",
         "Spring AOP: @Around for cross-cutting concerns"],
        "HIGH", 0.95, times_applied=65,
        context={"applies_to": ["Java", "Python", "TypeScript"], "gof": "Structural"}
    ),
    "dp_facade": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Facade: Simplified interface to complex subsystem. One entry point.",
        ["OrderFacade coordinates Order, Payment, Notification services",
         "Use when client needs 3+ services in sequence"],
        "MEDIUM", 0.94, times_applied=50,
        context={"applies_to": ["Java", "TypeScript", "Python"], "gof": "Structural"}
    ),
}

# ============================================================================
# BEHAVIORAL PATTERNS
# ============================================================================

BEHAVIORAL_PATTERNS = {
    "dp_strategy": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Strategy: Family of algorithms, interchangeable. Use when multiple ways exist.",
        ["Different AI providers as strategies — same interface, swap at runtime",
         "Functional: Comparator.comparing(item -> item.getPrice())"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["Java", "Python", "TypeScript"], "gof": "Behavioral"}
    ),
    "dp_observer": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Observer: Publish-subscribe for loose coupling. Events trigger handlers.",
        ["Spring: ApplicationEventPublisher + @EventListener",
         "React: useEffect for subscription",
         "Kafka: Consumer groups as observers"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["Java", "Node.js", "React", "Flutter"], "gof": "Behavioral"}
    ),
    "dp_command": _learning(
        "PATTERN", "DESIGN_PATTERNS",
        "Command: Encapsulate request as object. Enables undo/redo, queuing.",
        ["Each admin operation is a command with audit trail",
         "Command queue for async processing"],
        "MEDIUM", 0.93, times_applied=35,
        context={"applies_to": ["Java", "TypeScript"], "gof": "Behavioral"}
    ),
}

# ============================================================================
# ARCHITECTURAL PATTERNS
# ============================================================================

ARCHITECTURAL_PATTERNS = {
    "arch_clean_architecture": _learning(
        "PATTERN", "ARCHITECTURE",
        "Clean Architecture: Dependency rule — inner layers never depend on outer. "
        "Layers: Entities → Use Cases → Interface Adapters → Frameworks.",
        ["Domain has NO framework imports",
         "Use interfaces for dependency inversion",
         "@RestController calls use case, maps DTO ↔ domain"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Java", "TypeScript", "Python", "Dart"]}
    ),
    "arch_hexagonal": _learning(
        "PATTERN", "ARCHITECTURE",
        "Hexagonal (Ports & Adapters): Domain at center. Ports = interfaces. Adapters = implementations.",
        ["Port: interface UserRepository",
         "Adapter: JpaOrderRepository implements UserRepository",
         "Test: InMemoryOrderRepository for fast tests"],
        "HIGH", 0.93, times_applied=35,
        context={"applies_to": ["Java", "TypeScript"]}
    ),
    "arch_microservices": _learning(
        "PATTERN", "ARCHITECTURE",
        "Microservices: Each service owns data, communicates via API/events. "
        "Start monolith-first, extract at boundaries.",
        ["Service boundary: One service per domain aggregate",
         "Sync: REST/gRPC for queries, Async: events for commands",
         "Patterns: API Gateway, Circuit Breaker, Saga"],
        "HIGH", 0.93, times_applied=40,
        context={"applies_to": ["Spring Boot", "Node.js", "Go"]}
    ),
}

# ============================================================================
# DDD PATTERNS
# ============================================================================

DDD_PATTERNS = {
    "ddd_aggregate": _learning(
        "PATTERN", "DDD",
        "DDD Aggregates: Cluster with one root entity. All access through aggregate root.",
        ["Order (root) contains OrderItems — accessed only through Order",
         "One aggregate per transaction",
         "Cross-aggregate: use domain events"],
        "HIGH", 0.93, times_applied=35,
        context={"applies_to": ["Java", "TypeScript", "C#"]}
    ),
    "ddd_value_object": _learning(
        "PATTERN", "DDD",
        "Value Objects: Defined by attributes, immutable. Two VOs with same values are equal.",
        ["Java record Money(BigDecimal, Currency)",
         "TypeScript readonly Email type",
         "Use: order.total = Money.of(100, USD)"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Java", "TypeScript", "C#"]}
    ),
}

# ============================================================================
# PATTERN IMPLEMENTATIONS
# ============================================================================

DESIGN_PATTERNS = {
    "pat_repository": _pattern(
        "Repository", "ARCHITECTURE",
        "Abstract data access behind clean interface",
        "Data layer",
        "interface UserRepository { User save(User); Optional<User> findById(Long); }",
        "Java/TypeScript", 0.97, times_used=120
    ),
    "pat_unit_of_work": _pattern(
        "Unit of Work", "ARCHITECTURE",
        "Track changes during transaction, coordinate writes as single unit",
        "Complex transactions involving multiple repositories",
        "@Transactional public OrderResult placeOrder() { orderRepo.save(); paymentRepo.save(); }",
        "Java/Spring", 0.94, times_used=50
    ),
    "pat_circuit_breaker": _pattern(
        "Circuit Breaker", "RESILIENCE",
        "Prevent cascading failures by stopping calls to failing services",
        "External service calls, API integrations",
        "@CircuitBreaker(name='svc', fallbackMethod='fallback')",
        "Spring Boot + Resilience4j", 0.94, times_used=40
    ),
    "pat_retry": _pattern(
        "Retry with Backoff", "RESILIENCE",
        "Retry failed operations with increasing delays",
        "Network calls, API integrations",
        "@Retry(name='api', fallbackMethod='fallback')",
        "Java/Spring", 0.95, times_used=55
    ),
    "pat_specification": _pattern(
        "Specification", "DDD",
        "Encapsulate business rules as reusable predicates",
        "Complex filtering, validation, authorization",
        "interface Specification<T> { boolean isSatisfiedBy(T); }",
        "Java", 0.92, times_used=30
    ),
    "pat_mediator": _pattern(
        "Mediator/CQRS Handler", "ARCHITECTURE",
        "Route commands/queries to handlers through mediator",
        "CQRS implementations",
        "mediator.send(new CreateUserCommand(name, email))",
        "Java/TypeScript", 0.93, times_used=35
    ),
    "pat_event_bus": _pattern(
        "Event Bus", "ARCHITECTURE",
        "Publish domain events for loose coupling",
        "Cross-cutting concerns: audit, notifications",
        "eventBus.publish(new UserRegistered(user)); @EventListener void on(UserRegistered e) { ... }",
        "Java/Spring", 0.95, times_used=60
    ),
}

# Combined exports for backward compatibility
DESIGN_PATTERN_LEARNINGS = {
    **CREATIONAL_PATTERNS,
    **STRUCTURAL_PATTERNS,
    **BEHAVIORAL_PATTERNS,
    **ARCHITECTURAL_PATTERNS,
    **DDD_PATTERNS,
}