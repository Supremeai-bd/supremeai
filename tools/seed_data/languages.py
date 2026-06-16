"""
Part 2: Programming Languages Knowledge
Covers: Java, Python, JavaScript/TypeScript, Dart, Kotlin, Go, Rust, C#, SQL, Shell
~60 learnings + ~40 patterns = 100 documents
"""
from seed_data.helpers import _learning, _pattern

# ============================================================================
#  SYSTEM LEARNINGS - Language mastery
# ============================================================================

LANGUAGE_LEARNINGS = {

    # ── Java ───────────────────────────────────────────────────────────────
    "lang_java_streams": _learning(
        "PATTERN", "JAVA", "Java Streams API: Use .stream().filter().map().collect() for "
        "collection transformations. Parallel streams with .parallelStream() for CPU-bound "
        "tasks on large datasets (>10K elements). Avoid parallel streams for IO-bound work.",
        ["Use Collectors.toList(), toMap(), groupingBy() for terminal operations",
         "Prefer method references (String::toLowerCase) over lambdas when possible",
         "Use Optional.ofNullable() to avoid NPE in stream chains"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["Java 8+", "Spring Boot"], "version": "Java 17+"}
    ),
    "lang_java_records": _learning(
        "PATTERN", "JAVA", "Java Records (16+): Use 'record ClassName(Type field)' for "
        "immutable data carriers. Auto-generates equals(), hashCode(), toString(), getters. "
        "Perfect for DTOs, API responses, value objects. Cannot extend classes but can implement interfaces.",
        ["Replace POJOs with records for DTOs: record UserDTO(String name, String email) {}",
         "Use compact constructors for validation: record Age(int value) { Age { if(value<0) throw new IllegalArgumentException(); } }",
         "Records can have static fields and methods but no instance fields beyond components"],
        "MEDIUM", 0.95, times_applied=60,
        context={"applies_to": ["Java 16+", "Spring Boot 3+"], "replaces": "Lombok @Value"}
    ),
    "lang_java_sealed_classes": _learning(
        "PATTERN", "JAVA", "Sealed classes (Java 17+): 'sealed class Shape permits Circle, Rectangle' "
        "restricts which classes can extend. Enables exhaustive pattern matching in switch. "
        "Use for domain models with finite subtypes.",
        ["Combine with records: sealed interface Shape permits Circle, Rectangle {}; record Circle(double r) implements Shape {}",
         "Switch expressions with sealed types are exhaustive — no default needed",
         "Use 'non-sealed' keyword to re-open hierarchy for specific subtypes"],
        "MEDIUM", 0.93, times_applied=25,
        context={"applies_to": ["Java 17+"], "use_case": "Domain modeling, state machines"}
    ),
    "lang_java_virtual_threads": _learning(
        "PATTERN", "JAVA", "Virtual Threads (Java 21+): Use Executors.newVirtualThreadPerTaskExecutor() "
        "for high-concurrency IO-bound tasks. 1M+ virtual threads possible. Don't use for "
        "CPU-bound work. Spring Boot 3.2+ supports virtual threads via spring.threads.virtual.enabled=true.",
        ["Enable in Spring Boot: spring.threads.virtual.enabled=true",
         "Replace thread pools with virtual threads for HTTP clients, DB calls",
         "Avoid synchronized blocks in virtual thread code — use ReentrantLock instead",
         "Don't pool virtual threads — create new ones per task"],
        "HIGH", 0.94, times_applied=30,
        context={"applies_to": ["Java 21+", "Spring Boot 3.2+"], "performance": "10x throughput for IO"}
    ),
    "lang_java_optional": _learning(
        "PATTERN", "JAVA", "Optional usage: Return Optional<T> from methods that might not find a result. "
        "Never use Optional as method parameter or field. Use orElseThrow() for required values, "
        "orElse() for defaults, map()/flatMap() for transformations.",
        ["Service: return Optional.ofNullable(repository.findById(id))",
         "Controller: .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND))",
         "Never: Optional<String> name as a parameter — use @Nullable or overloading instead",
         "Chain: optional.map(User::getName).orElse(\"Anonymous\")"],
        "HIGH", 0.97, times_applied=120,
        context={"applies_to": ["Java 8+"], "anti_pattern": "Optional.get() without isPresent()"}
    ),
    "lang_java_generics": _learning(
        "PATTERN", "JAVA", "Generics best practices: Use bounded wildcards — '? extends T' for "
        "producers (read), '? super T' for consumers (write). PECS principle. Use type inference "
        "with diamond operator. Generic methods over generic classes when possible.",
        ["Producer: List<? extends Number> — can read Number, can't add",
         "Consumer: List<? super Integer> — can add Integer, reads as Object",
         "Generic method: <T extends Comparable<T>> T max(T a, T b)",
         "Type erasure means no 'new T()' or 'instanceof T' at runtime"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["Java 5+"], "principle": "PECS: Producer Extends, Consumer Super"}
    ),
    "lang_java_exceptions": _learning(
        "PATTERN", "JAVA", "Exception handling: Use unchecked exceptions (RuntimeException subclasses) "
        "for programming errors. Checked exceptions only for recoverable conditions the caller must "
        "handle. Create domain-specific exceptions. Use @ControllerAdvice for global handling in Spring.",
        ["Create: class OrderNotFoundException extends RuntimeException { OrderNotFoundException(Long id) { super(\"Order not found: \" + id); } }",
         "Global handler: @ExceptionHandler(OrderNotFoundException.class) returns 404",
         "Never catch Exception or Throwable — catch specific types",
         "Use try-with-resources for ALL Closeable resources"],
        "HIGH", 0.96, times_applied=95,
        context={"applies_to": ["Java", "Spring Boot"]}
    ),

    # ── Python ─────────────────────────────────────────────────────────────
    "lang_python_typing": _learning(
        "PATTERN", "PYTHON", "Python type hints: Use typing module for all function signatures. "
        "dict[str, Any], list[int], Optional[str], Union[str, int]. Use TypedDict for dict shapes. "
        "Pydantic BaseModel for runtime validation. mypy for static checking.",
        ["Function: def get_user(user_id: int) -> Optional[User]:",
         "TypedDict: class UserDict(TypedDict): name: str; age: int",
         "Pydantic: class UserCreate(BaseModel): name: str; email: EmailStr",
         "Run mypy: mypy --strict src/"],
        "HIGH", 0.95, times_applied=75,
        context={"applies_to": ["Python 3.9+", "FastAPI", "Django"]}
    ),
    "lang_python_async": _learning(
        "PATTERN", "PYTHON", "Python async/await: Use asyncio for IO-bound concurrency. "
        "async def + await for coroutines. asyncio.gather() for parallel IO. "
        "aiohttp for async HTTP, asyncpg for async PostgreSQL. Never mix sync blocking calls in async code.",
        ["Parallel IO: results = await asyncio.gather(fetch_a(), fetch_b(), fetch_c())",
         "Async HTTP: async with aiohttp.ClientSession() as session: resp = await session.get(url)",
         "FastAPI: async def endpoint() is automatically async",
         "Use asyncio.to_thread() to run sync code in async context"],
        "HIGH", 0.94, times_applied=55,
        context={"applies_to": ["Python 3.7+", "FastAPI", "aiohttp"]}
    ),
    "lang_python_decorators": _learning(
        "PATTERN", "PYTHON", "Python decorators: Functions that wrap other functions. Use @functools.wraps "
        "to preserve metadata. Common patterns: @lru_cache for memoization, @property for computed attrs, "
        "@staticmethod/@classmethod for alternate constructors.",
        ["Decorator: def timer(func): @wraps(func) def wrapper(*args, **kw): start=time.time(); r=func(*args,**kw); print(time.time()-start); return r; return wrapper",
         "@lru_cache(maxsize=128) for expensive pure functions",
         "@dataclass(frozen=True) for immutable data classes",
         "Decorator with args: def retry(times): def decorator(func): ... return decorator"],
        "MEDIUM", 0.95, times_applied=65,
        context={"applies_to": ["Python 3+"]}
    ),
    "lang_python_comprehensions": _learning(
        "PATTERN", "PYTHON", "Python comprehensions: List [x for x in items if cond], Dict {k:v for k,v in pairs}, "
        "Set {x for x in items}, Generator (x for x in items). Use comprehensions over map/filter. "
        "Keep them single-line readable — use regular loops for complex logic.",
        ["List: names = [u.name for u in users if u.active]",
         "Dict: scores = {s.name: s.grade for s in students}",
         "Nested: flat = [x for row in matrix for x in row]",
         "Generator for large data: sum(x*x for x in range(1000000))"],
        "MEDIUM", 0.97, times_applied=100,
        context={"applies_to": ["Python 3+"]}
    ),
    "lang_python_dataclasses": _learning(
        "PATTERN", "PYTHON", "Python dataclasses: @dataclass auto-generates __init__, __repr__, __eq__. "
        "Use frozen=True for immutable. field(default_factory=list) for mutable defaults. "
        "Use __post_init__ for validation. For API models, prefer Pydantic over dataclass.",
        ["Basic: @dataclass class User: name: str; age: int; active: bool = True",
         "Immutable: @dataclass(frozen=True) class Point: x: float; y: float",
         "Validation: def __post_init__(self): if self.age < 0: raise ValueError",
         "Mutable default: items: list = field(default_factory=list)"],
        "MEDIUM", 0.96, times_applied=70,
        context={"applies_to": ["Python 3.7+"], "alternative": "Pydantic for validation"}
    ),

    # ── JavaScript/TypeScript ──────────────────────────────────────────────
    "lang_js_async_patterns": _learning(
        "PATTERN", "JAVASCRIPT", "JS async patterns: async/await over .then() chains. "
        "Promise.all() for parallel, Promise.allSettled() when some can fail, Promise.race() for "
        "timeouts. Use AbortController for cancellation. Handle errors with try/catch, not .catch().",
        ["Parallel: const [users, posts] = await Promise.all([fetchUsers(), fetchPosts()])",
         "Timeout: const result = await Promise.race([fetch(url), timeout(5000)])",
         "Cancel: const ctrl = new AbortController(); fetch(url, {signal: ctrl.signal})",
         "Error: try { await api() } catch(e) { if(e.name === 'AbortError') return; throw e; }"],
        "HIGH", 0.96, times_applied=90,
        context={"applies_to": ["JavaScript", "TypeScript", "Node.js", "React"]}
    ),
    "lang_ts_utility_types": _learning(
        "PATTERN", "TYPESCRIPT", "TypeScript utility types: Partial<T> all optional, Required<T> all required, "
        "Pick<T,'a'|'b'> subset, Omit<T,'c'> exclude, Record<K,V> map type, Readonly<T>, "
        "Extract/Exclude for union filtering. Use these over manual type definitions.",
        ["Update DTO: type UserUpdate = Partial<User>",
         "Create DTO: type UserCreate = Omit<User, 'id' | 'createdAt'>",
         "API response: type ApiResponse<T> = { data: T; error?: string; status: number }",
         "Discriminated union: type Result<T> = { ok: true; value: T } | { ok: false; error: Error }"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["TypeScript 4+", "React", "Node.js"]}
    ),
    "lang_ts_strict_mode": _learning(
        "PATTERN", "TYPESCRIPT", "TypeScript strict mode: Enable strict: true in tsconfig.json. "
        "Includes strictNullChecks, noImplicitAny, strictFunctionTypes. Use 'unknown' over 'any'. "
        "Narrow types with type guards: typeof, instanceof, 'prop' in obj, discriminated unions.",
        ["tsconfig: {compilerOptions: {strict: true, noUncheckedIndexedAccess: true}}",
         "Type guard: function isUser(x: unknown): x is User { return typeof x === 'object' && x !== null && 'name' in x }",
         "Narrow: if (result.kind === 'success') result.data // TypeScript knows it's SuccessResult",
         "Use satisfies operator: const config = {...} satisfies Config"],
        "HIGH", 0.96, times_applied=60,
        context={"applies_to": ["TypeScript 4.9+"], "key_setting": "strict: true"}
    ),
    "lang_js_es_modules": _learning(
        "PATTERN", "JAVASCRIPT", "ES Modules: Use import/export over require/module.exports. "
        "Named exports for utilities: export function helper(). Default export for main class/component. "
        "Dynamic import() for code splitting. In Node.js: set type:module in package.json or use .mjs.",
        ["Named: export const API_URL = '...'; import { API_URL } from './config'",
         "Default: export default class UserService {}; import UserService from './UserService'",
         "Dynamic: const module = await import('./heavy-module')",
         "Re-export: export { default as Button } from './Button'"],
        "MEDIUM", 0.95, times_applied=80,
        context={"applies_to": ["JavaScript", "TypeScript", "Node.js 14+", "React", "Vite"]}
    ),

    # ── Dart / Flutter ─────────────────────────────────────────────────────
    "lang_dart_null_safety": _learning(
        "PATTERN", "DART", "Dart null safety: All types non-nullable by default. Use String? for nullable. "
        "Late keyword for deferred initialization. Use ?. for null-aware access, ?? for defaults, "
        "! for force-unwrap (only when certain). Required keyword for named parameters.",
        ["Nullable: String? name; // can be null",
         "Null-aware: final len = name?.length ?? 0;",
         "Late: late final String token; // initialized before use",
         "Required: void greet({required String name}) {}",
         "Null check pattern: if (name case String n) print(n.length);"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["Dart 2.12+", "Flutter 2+"]}
    ),
    "lang_dart_freezed": _learning(
        "PATTERN", "DART", "Dart Freezed package: Code generation for immutable models with "
        "copyWith, ==, hashCode, toString, JSON serialization. Use @freezed for immutable, "
        "@unfreezed for mutable. Combines with json_serializable for fromJson/toJson.",
        ["Model: @freezed class User with _$User { factory User({required String name, required int age}) = _User; factory User.fromJson(Map<String,dynamic> json) => _$UserFromJson(json); }",
         "CopyWith: final updated = user.copyWith(name: 'New Name');",
         "Union types: @freezed class AuthState { factory AuthState.authenticated(User user) = Authenticated; factory AuthState.unauthenticated() = Unauthenticated; }",
         "Run: dart run build_runner build --delete-conflicting-outputs"],
        "HIGH", 0.94, times_applied=50,
        context={"applies_to": ["Dart", "Flutter"], "packages": ["freezed", "freezed_annotation", "json_serializable"]}
    ),
    "lang_dart_riverpod": _learning(
        "PATTERN", "DART", "Riverpod state management: Compile-safe, testable, no BuildContext needed. "
        "Use @riverpod annotation for code generation. Provider types: Provider (sync), FutureProvider (async), "
        "NotifierProvider (stateful), StreamProvider (streams).",
        ["Simple: @riverpod String greeting(GreetingRef ref) => 'Hello';",
         "Async: @riverpod Future<List<User>> users(UsersRef ref) async => fetchUsers();",
         "Stateful: @riverpod class Counter extends _$Counter { @override int build() => 0; void increment() => state++; }",
         "Consume: ref.watch(usersProvider).when(data: (d)=>..., error: (e,s)=>..., loading: ()=>...)"],
        "HIGH", 0.93, times_applied=40,
        context={"applies_to": ["Flutter", "Dart"], "version": "Riverpod 2.0+"}
    ),

    # ── Kotlin ─────────────────────────────────────────────────────────────
    "lang_kotlin_coroutines": _learning(
        "PATTERN", "KOTLIN", "Kotlin Coroutines: Lightweight concurrency. launch{} for fire-and-forget, "
        "async{}/await() for results, withContext(Dispatchers.IO) for IO work. "
        "Use structured concurrency with coroutineScope{}. Flow for reactive streams.",
        ["Launch: viewModelScope.launch { val user = repository.getUser() }",
         "Async: val (a, b) = coroutineScope { async{getA()} to async{getB()} }; a.await() + b.await()",
         "IO: withContext(Dispatchers.IO) { database.query() }",
         "Flow: fun getUsers(): Flow<List<User>> = flow { emit(api.fetchUsers()) }"],
        "HIGH", 0.95, times_applied=55,
        context={"applies_to": ["Kotlin", "Android", "Ktor"]}
    ),
    "lang_kotlin_data_class": _learning(
        "PATTERN", "KOTLIN", "Kotlin data classes: Concise immutable models with auto-generated "
        "equals(), hashCode(), toString(), copy(), componentN(). Use sealed classes for state machines. "
        "Use value classes for type-safe wrappers with zero overhead.",
        ["Data: data class User(val name: String, val age: Int)",
         "Copy: val updated = user.copy(name = \"New\")",
         "Sealed: sealed class Result<T> { data class Success<T>(val data: T): Result<T>(); data class Failure(val error: Throwable): Result<Nothing>() }",
         "Value: @JvmInline value class Email(val value: String)"],
        "MEDIUM", 0.96, times_applied=70,
        context={"applies_to": ["Kotlin", "Android", "Spring Boot"]}
    ),

    # ── Go ─────────────────────────────────────────────────────────────────
    "lang_go_error_handling": _learning(
        "PATTERN", "GO", "Go error handling: Return (result, error) tuples. Check errors immediately. "
        "Use fmt.Errorf with %w for wrapping. errors.Is/As for comparison. Custom error types with "
        "Error() string method. Never ignore errors with _.",
        ["Return: func getUser(id int) (*User, error) { if id <= 0 { return nil, fmt.Errorf(\"invalid id: %d\", id) } }",
         "Wrap: return fmt.Errorf(\"getUser: %w\", err)",
         "Check: if errors.Is(err, sql.ErrNoRows) { return nil, ErrNotFound }",
         "Custom: type NotFoundError struct { ID int }; func (e NotFoundError) Error() string { return fmt.Sprintf(\"not found: %d\", e.ID) }"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["Go 1.13+"]}
    ),
    "lang_go_concurrency": _learning(
        "PATTERN", "GO", "Go concurrency: goroutines + channels. Use 'go func(){}()' for goroutines. "
        "Channels for communication: ch := make(chan Type). Select for multiplexing. "
        "sync.WaitGroup for coordination. context.Context for cancellation and timeouts.",
        ["Worker pool: for i := 0; i < workers; i++ { go func() { for job := range jobs { results <- process(job) } }() }",
         "Select: select { case msg := <-ch: handle(msg); case <-ctx.Done(): return ctx.Err() }",
         "WaitGroup: var wg sync.WaitGroup; wg.Add(n); go func(){defer wg.Done(); work()}(); wg.Wait()",
         "Timeout: ctx, cancel := context.WithTimeout(ctx, 5*time.Second); defer cancel()"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Go"]}
    ),

    # ── Rust ───────────────────────────────────────────────────────────────
    "lang_rust_ownership": _learning(
        "PATTERN", "RUST", "Rust ownership: Each value has one owner. Ownership moves on assignment. "
        "Borrow with & (immutable) or &mut (mutable, exclusive). Lifetimes ensure references are valid. "
        "Clone for explicit copies. Use Arc<Mutex<T>> for shared mutable state across threads.",
        ["Move: let s2 = s1; // s1 is now invalid",
         "Borrow: fn len(s: &str) -> usize { s.len() } // immutable borrow",
         "Mut borrow: fn push(v: &mut Vec<i32>) { v.push(42); } // exclusive access",
         "Clone: let s2 = s1.clone(); // both valid, explicit copy"],
        "HIGH", 0.93, times_applied=30,
        context={"applies_to": ["Rust"], "key_concept": "Borrow checker"}
    ),

    # ── C# ─────────────────────────────────────────────────────────────────
    "lang_csharp_linq": _learning(
        "PATTERN", "CSHARP", "C# LINQ: Query collections fluently. Method syntax preferred: "
        ".Where(x => x.Active).Select(x => x.Name).ToList(). Deferred execution — enumerate once. "
        "Use async variants: await collection.ToListAsync(). IQueryable for database, IEnumerable for memory.",
        ["Filter+Map: var names = users.Where(u => u.Age > 18).Select(u => u.Name).ToList();",
         "Group: var byDept = employees.GroupBy(e => e.Dept).Select(g => new { Dept = g.Key, Count = g.Count() });",
         "Join: var result = orders.Join(products, o => o.ProductId, p => p.Id, (o, p) => new { o.Qty, p.Name });",
         "Async (EF): var users = await db.Users.Where(u => u.Active).ToListAsync();"],
        "HIGH", 0.95, times_applied=65,
        context={"applies_to": ["C#", ".NET", "Entity Framework"]}
    ),
    "lang_csharp_records": _learning(
        "PATTERN", "CSHARP", "C# records: Immutable reference types with value equality. "
        "record class for reference, record struct for value type. With-expressions for copies. "
        "Perfect for DTOs, events, domain objects.",
        ["Simple: public record User(string Name, int Age);",
         "With: var updated = user with { Name = \"New\" };",
         "Record struct: public readonly record struct Point(double X, double Y);",
         "Deconstruct: var (name, age) = user;"],
        "MEDIUM", 0.94, times_applied=35,
        context={"applies_to": ["C# 9+", ".NET 5+"]}
    ),

    # ── Shell / Bash ───────────────────────────────────────────────────────
    "lang_bash_best_practices": _learning(
        "PATTERN", "SHELL", "Bash best practices: Always set -euo pipefail at top. Quote all variables \"$var\". "
        "Use [[ ]] over [ ]. Use local variables in functions. Shellcheck for linting. "
        "Prefer printf over echo for portability.",
        ["Header: #!/usr/bin/env bash; set -euo pipefail",
         "Variables: readonly CONFIG_DIR=\"${HOME}/.config\"; local result=\"$(command)\"",
         "Conditionals: [[ -f \"$file\" ]] && [[ \"$str\" == \"expected\" ]]",
         "Arrays: declare -a items=(\"one\" \"two\"); for item in \"${items[@]}\"; do echo \"$item\"; done"],
        "HIGH", 0.96, times_applied=80,
        context={"applies_to": ["Bash", "Shell scripts", "CI/CD pipelines"]}
    ),

    # ── SQL ────────────────────────────────────────────────────────────────
    "lang_sql_optimization": _learning(
        "PATTERN", "SQL", "SQL optimization: Use indexes on WHERE/JOIN/ORDER BY columns. "
        "EXPLAIN ANALYZE to check query plans. Avoid SELECT * — list needed columns. "
        "Use CTEs for readability. Batch inserts (VALUES lists). Parameterized queries always.",
        ["Index: CREATE INDEX idx_users_email ON users(email);",
         "CTE: WITH active AS (SELECT * FROM users WHERE active) SELECT * FROM active JOIN orders ...",
         "Batch: INSERT INTO users (name, email) VALUES ('a','a@x'), ('b','b@x'), ('c','c@x');",
         "NEVER: SELECT * FROM users WHERE name = '\" + input + \"' -- SQL injection!"],
        "CRITICAL", 0.97, times_applied=100,
        context={"applies_to": ["PostgreSQL", "MySQL", "SQLite"], "security": "Always use parameterized queries"}
    ),
    "lang_sql_window_functions": _learning(
        "PATTERN", "SQL", "SQL window functions: ROW_NUMBER(), RANK(), DENSE_RANK() for numbering. "
        "LAG/LEAD for prev/next row. SUM/AVG OVER(PARTITION BY) for running totals. "
        "NTILE for bucketing. PARTITION BY groups, ORDER BY sorts within each group.",
        ["Row number: SELECT *, ROW_NUMBER() OVER(PARTITION BY dept ORDER BY salary DESC) rn FROM employees",
         "Running total: SELECT date, amount, SUM(amount) OVER(ORDER BY date) running_total FROM sales",
         "Prev value: SELECT date, value, LAG(value) OVER(ORDER BY date) prev_value FROM metrics",
         "Top N per group: WITH ranked AS (SELECT *, ROW_NUMBER() OVER(PARTITION BY category ORDER BY score DESC) rn FROM items) SELECT * FROM ranked WHERE rn <= 3"],
        "HIGH", 0.94, times_applied=50,
        context={"applies_to": ["PostgreSQL", "MySQL 8+", "SQLite 3.25+"]}
    ),
}

# ============================================================================
#  PATTERNS - Language-specific code patterns
# ============================================================================

LANGUAGE_PATTERNS = {

    # ── Java Patterns ──────────────────────────────────────────────────────
    "pat_java_builder": _pattern(
        "Java Builder Pattern", "JAVA",
        "Builder pattern for complex object construction with fluent API",
        "When constructors have 4+ parameters or optional fields",
        "public class User { private String name; private int age; public static class Builder { private String name; private int age; public Builder name(String n) { this.name=n; return this; } public Builder age(int a) { this.age=a; return this; } public User build() { User u = new User(); u.name=this.name; u.age=this.age; return u; } } }",
        "Java", 0.95, times_used=80
    ),
    "pat_java_repository": _pattern(
        "Spring Data Repository", "JAVA",
        "Repository interface with custom query methods following Spring Data naming conventions",
        "Data access layer in Spring Boot applications",
        "public interface UserRepository extends JpaRepository<User, Long> { Optional<User> findByEmail(String email); List<User> findByActiveTrue(); @Query(\"SELECT u FROM User u WHERE u.createdAt > :date\") List<User> findRecentUsers(@Param(\"date\") LocalDateTime date); }",
        "Spring Boot", 0.97, times_used=120
    ),
    "pat_java_service_layer": _pattern(
        "Service Layer Pattern", "JAVA",
        "Transactional service with dependency injection, validation, and error handling",
        "Business logic layer in Spring Boot",
        "@Service @RequiredArgsConstructor public class UserService { private final UserRepository repo; private final PasswordEncoder encoder; @Transactional public User create(CreateUserDTO dto) { if(repo.existsByEmail(dto.email())) throw new DuplicateException(); User u = new User(); u.setEmail(dto.email()); u.setPassword(encoder.encode(dto.password())); return repo.save(u); } }",
        "Spring Boot", 0.97, times_used=130
    ),

    # ── Python Patterns ────────────────────────────────────────────────────
    "pat_python_fastapi_crud": _pattern(
        "FastAPI CRUD Router", "PYTHON",
        "Complete CRUD router with Pydantic models, dependency injection, and error handling",
        "REST API endpoints in FastAPI",
        "router = APIRouter(prefix='/users', tags=['users'])\n@router.get('/', response_model=list[UserOut])\nasync def list_users(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):\n    return db.query(User).offset(skip).limit(limit).all()\n@router.post('/', response_model=UserOut, status_code=201)\nasync def create_user(user: UserCreate, db: Session = Depends(get_db)):\n    db_user = User(**user.dict()); db.add(db_user); db.commit(); return db_user",
        "FastAPI", 0.96, times_used=70
    ),
    "pat_python_context_manager": _pattern(
        "Context Manager Pattern", "PYTHON",
        "Custom context manager for resource management using __enter__/__exit__ or @contextmanager",
        "Database connections, file handling, temporary state",
        "@contextmanager\ndef managed_connection(url):\n    conn = create_connection(url)\n    try:\n        yield conn\n    finally:\n        conn.close()\n# Usage: with managed_connection(url) as conn: conn.execute(query)",
        "Python", 0.95, times_used=55
    ),

    # ── TypeScript Patterns ────────────────────────────────────────────────
    "pat_ts_api_client": _pattern(
        "TypeScript API Client", "TYPESCRIPT",
        "Type-safe API client with interceptors, error handling, and generic request methods",
        "Frontend or backend HTTP client",
        "class ApiClient { constructor(private baseUrl: string, private token?: string) {} private async request<T>(method: string, path: string, body?: unknown): Promise<T> { const res = await fetch(`${this.baseUrl}${path}`, { method, headers: {'Content-Type':'application/json', ...(this.token && {'Authorization':`Bearer ${this.token}`})}, body: body ? JSON.stringify(body) : undefined }); if(!res.ok) throw new ApiError(res.status, await res.text()); return res.json(); } get<T>(path: string) { return this.request<T>('GET', path); } post<T>(path: string, body: unknown) { return this.request<T>('POST', path, body); } }",
        "TypeScript", 0.95, times_used=60
    ),
    "pat_ts_react_hook": _pattern(
        "React Custom Hook", "TYPESCRIPT",
        "Custom React hook with loading/error states and TypeScript generics",
        "Reusable data fetching or state logic in React",
        "function useAsync<T>(asyncFn: () => Promise<T>, deps: unknown[] = []) { const [state, setState] = useState<{data?:T; error?:Error; loading:boolean}>({loading:true}); useEffect(() => { let cancelled = false; setState({loading:true}); asyncFn().then(data => { if(!cancelled) setState({data, loading:false}); }).catch(error => { if(!cancelled) setState({error, loading:false}); }); return () => { cancelled = true; }; }, deps); return state; }",
        "React", 0.96, times_used=75
    ),

    # ── Dart/Flutter Patterns ──────────────────────────────────────────────
    "pat_dart_repository": _pattern(
        "Flutter Repository Pattern", "DART",
        "Repository abstraction over data sources (API + local cache) with error handling",
        "Data layer in Flutter apps",
        "abstract class UserRepository { Future<List<User>> getUsers(); Future<User> getUserById(String id); }\nclass UserRepositoryImpl implements UserRepository { final ApiClient api; final LocalCache cache; UserRepositoryImpl(this.api, this.cache);\n  @override Future<List<User>> getUsers() async { try { final users = await api.fetchUsers(); await cache.saveUsers(users); return users; } catch (_) { return cache.getUsers(); } } }",
        "Flutter", 0.94, times_used=45
    ),
    "pat_dart_bloc": _pattern(
        "Flutter BLoC Pattern", "DART",
        "Business Logic Component with events, states, and stream transformations",
        "Complex state management in Flutter",
        "// Events\nsealed class AuthEvent {}\nclass LoginRequested extends AuthEvent { final String email, password; LoginRequested(this.email, this.password); }\n// States\nsealed class AuthState {}\nclass AuthInitial extends AuthState {}\nclass AuthLoading extends AuthState {}\nclass AuthSuccess extends AuthState { final User user; AuthSuccess(this.user); }\nclass AuthFailure extends AuthState { final String message; AuthFailure(this.message); }\n// BLoC\nclass AuthBloc extends Bloc<AuthEvent, AuthState> { AuthBloc(this.repo) : super(AuthInitial()) { on<LoginRequested>(_onLogin); } }",
        "Flutter", 0.94, times_used=50
    ),

    # ── Go Patterns ────────────────────────────────────────────────────────
    "pat_go_http_handler": _pattern(
        "Go HTTP Handler", "GO",
        "HTTP handler with middleware, JSON encoding, and proper error responses",
        "REST API endpoints in Go",
        "func handleGetUser(svc UserService) http.HandlerFunc { return func(w http.ResponseWriter, r *http.Request) { id := chi.URLParam(r, \"id\"); user, err := svc.GetByID(r.Context(), id); if err != nil { if errors.Is(err, ErrNotFound) { http.Error(w, \"not found\", 404); return }; http.Error(w, \"internal error\", 500); return }; w.Header().Set(\"Content-Type\",\"application/json\"); json.NewEncoder(w).Encode(user) } }",
        "Go", 0.94, times_used=40
    ),

    # ── Kotlin Patterns ───────────────────────────────────────────────────
    "pat_kotlin_viewmodel": _pattern(
        "Android ViewModel", "KOTLIN",
        "ViewModel with StateFlow, coroutines, and repository pattern",
        "UI state management in Android",
        "class UserViewModel(private val repo: UserRepository) : ViewModel() { private val _state = MutableStateFlow<UiState<List<User>>>(UiState.Loading); val state: StateFlow<UiState<List<User>>> = _state.asStateFlow(); init { loadUsers() }; private fun loadUsers() { viewModelScope.launch { _state.value = UiState.Loading; try { _state.value = UiState.Success(repo.getUsers()) } catch(e: Exception) { _state.value = UiState.Error(e.message ?: \"Unknown\") } } } }",
        "Android/Kotlin", 0.95, times_used=55
    ),
}
