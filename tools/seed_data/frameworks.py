"""
Part 3: Frameworks Knowledge
Covers: Spring Boot, React, Flutter, Node.js/Express, FastAPI, Django, Next.js, Angular, NestJS
~50 learnings + ~30 patterns + ~20 templates = 100 documents
"""
from seed_data.helpers import _learning, _pattern, _code_template

FRAMEWORK_LEARNINGS = {

    # ── Spring Boot ────────────────────────────────────────────────────────
    "fw_spring_boot_structure": _learning(
        "PATTERN", "SPRING_BOOT",
        "Spring Boot project structure: src/main/java/{pkg}/{controller,service,model,repository,config,dto,exception}. "
        "Application.java at root. application.yml for config. Use @SpringBootApplication on main class. "
        "Component scanning auto-detects @Service, @Controller, @Repository, @Component.",
        ["Controller: @RestController @RequestMapping(\"/api/v1/users\")",
         "Service: @Service + @Transactional for business logic",
         "Repository: extends JpaRepository<Entity, ID> for data access",
         "Config: @Configuration + @Bean for third-party beans",
         "DTO: Java records for request/response payloads"],
        "HIGH", 0.97, times_applied=140,
        context={"applies_to": ["Spring Boot 3+", "Java 17+"], "build_tool": "Gradle/Maven"}
    ),
    "fw_spring_security": _learning(
        "PATTERN", "SPRING_BOOT",
        "Spring Security 6+: SecurityFilterChain bean replaces WebSecurityConfigurerAdapter. "
        "JWT auth: OncePerRequestFilter extracts token → validates → sets SecurityContext. "
        "Use @PreAuthorize for method-level security. CORS config in SecurityFilterChain.",
        ["Config: @Bean SecurityFilterChain filterChain(HttpSecurity http) { return http.csrf(c->c.disable()).sessionManagement(s->s.sessionCreationPolicy(STATELESS)).authorizeHttpRequests(a->a.requestMatchers(\"/api/auth/**\").permitAll().anyRequest().authenticated()).addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class).build(); }",
         "JWT Filter: extract token from Authorization header → validate → UsernamePasswordAuthenticationToken",
         "Method security: @PreAuthorize(\"hasRole('ADMIN')\") on controller methods",
         "CORS: .cors(c -> c.configurationSource(corsConfig()))"],
        "CRITICAL", 0.96, times_applied=90,
        context={"applies_to": ["Spring Boot 3+", "Spring Security 6+"], "replaces": "WebSecurityConfigurerAdapter"}
    ),
    "fw_spring_data_jpa": _learning(
        "PATTERN", "SPRING_BOOT",
        "Spring Data JPA: Define interface extending JpaRepository. Method name queries: "
        "findByEmailAndActive(String email, boolean active). @Query for complex queries. "
        "Projections for partial selects. Specification for dynamic queries. Pageable for pagination.",
        ["Query methods: findByStatusIn(List<Status> statuses), findByCreatedAtAfter(LocalDateTime date)",
         "Pagination: Page<User> findByActive(boolean active, Pageable pageable)",
         "Custom: @Query(\"SELECT new com.dto.UserSummary(u.name, u.email) FROM User u WHERE u.active = true\")",
         "Specification: where(hasName(name)).and(isActive())"],
        "HIGH", 0.96, times_applied=100,
        context={"applies_to": ["Spring Boot", "JPA", "Hibernate"]}
    ),
    "fw_spring_validation": _learning(
        "PATTERN", "SPRING_BOOT",
        "Spring Validation: @Valid on @RequestBody. Use Jakarta validation annotations: "
        "@NotBlank, @Email, @Size, @Min, @Max, @Pattern. Custom validators with @Constraint. "
        "MethodArgumentNotValidException handled by @ControllerAdvice.",
        ["DTO: record CreateUser(@NotBlank String name, @Email String email, @Size(min=8) String password) {}",
         "Controller: @PostMapping public User create(@Valid @RequestBody CreateUser dto)",
         "Custom: @Constraint(validatedBy=PhoneValidator.class) @interface ValidPhone {}",
         "Error handler: @ExceptionHandler(MethodArgumentNotValidException.class) returns field errors"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["Spring Boot 3+", "Jakarta Validation"]}
    ),
    "fw_spring_actuator": _learning(
        "PATTERN", "SPRING_BOOT",
        "Spring Actuator: Health checks, metrics, info endpoints. Enable with spring-boot-starter-actuator. "
        "Expose specific endpoints: management.endpoints.web.exposure.include=health,info,metrics,prometheus. "
        "Custom health indicators with HealthIndicator interface. Prometheus integration for monitoring.",
        ["Config: management.endpoints.web.exposure.include=health,info,prometheus",
         "Custom: @Component class DbHealthIndicator implements HealthIndicator { Health health() { return db.isConnected() ? Health.up().build() : Health.down().build(); } }",
         "Prometheus: add micrometer-registry-prometheus dependency",
         "Info: management.info.env.enabled=true + info.app.name=SupremeAI in yml"],
        "MEDIUM", 0.94, times_applied=50,
        context={"applies_to": ["Spring Boot 3+"], "monitoring": ["Prometheus", "Grafana"]}
    ),

    # ── React ──────────────────────────────────────────────────────────────
    "fw_react_hooks": _learning(
        "PATTERN", "REACT",
        "React Hooks: useState for local state, useEffect for side effects (cleanup!), "
        "useCallback for stable callbacks, useMemo for expensive computations, useRef for DOM/values. "
        "Custom hooks extract reusable logic. Rules: only call at top level, only in components/hooks.",
        ["State: const [users, setUsers] = useState<User[]>([])",
         "Effect: useEffect(() => { const ctrl = new AbortController(); fetchData(ctrl.signal); return () => ctrl.abort(); }, [id])",
         "Callback: const handleClick = useCallback((id: string) => setSelected(id), [])",
         "Custom: function useDebounce<T>(value: T, delay: number): T { ... }"],
        "HIGH", 0.97, times_applied=150,
        context={"applies_to": ["React 18+", "TypeScript"]}
    ),
    "fw_react_state_management": _learning(
        "PATTERN", "REACT",
        "React state management tiers: (1) useState for component state, (2) useContext for "
        "theme/auth/locale, (3) Zustand/Jotai for client state, (4) TanStack Query for server state. "
        "Don't use Redux for new projects — Zustand is simpler. TanStack Query replaces most useEffect data fetching.",
        ["Server state: const { data, isLoading } = useQuery({ queryKey: ['users'], queryFn: fetchUsers })",
         "Client state: const useStore = create<State>((set) => ({ count: 0, inc: () => set(s => ({ count: s.count + 1 })) }))",
         "Context: const ThemeContext = createContext<Theme>('light'); <ThemeContext.Provider value={theme}>",
         "Mutation: const mutation = useMutation({ mutationFn: createUser, onSuccess: () => queryClient.invalidateQueries(['users']) })"],
        "HIGH", 0.95, times_applied=80,
        context={"applies_to": ["React 18+"], "recommended": ["TanStack Query", "Zustand"]}
    ),
    "fw_react_performance": _learning(
        "PATTERN", "REACT",
        "React performance: React.memo for pure components. useMemo/useCallback to prevent re-renders. "
        "React.lazy + Suspense for code splitting. Use React DevTools Profiler. Virtualize long lists "
        "with react-window. Avoid inline objects/arrays in JSX props.",
        ["Memo: const UserCard = React.memo(({ user }: { user: User }) => <div>{user.name}</div>)",
         "Lazy: const Dashboard = React.lazy(() => import('./Dashboard'))",
         "Virtual: <FixedSizeList height={600} width={400} itemSize={50} itemCount={items.length}>{Row}</FixedSizeList>",
         "Key: Always use stable IDs as keys, never array index for dynamic lists"],
        "HIGH", 0.95, times_applied=70,
        context={"applies_to": ["React 18+"], "tools": ["React DevTools", "react-window"]}
    ),
    "fw_react_forms": _learning(
        "PATTERN", "REACT",
        "React forms: Use react-hook-form for performance (uncontrolled inputs). "
        "Zod for schema validation with zodResolver. Use FormProvider for nested forms. "
        "Controlled inputs only when you need real-time validation display.",
        ["Setup: const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) })",
         "Schema: const schema = z.object({ email: z.string().email(), password: z.string().min(8) })",
         "Submit: <form onSubmit={handleSubmit(onSubmit)}><input {...register('email')} />",
         "Error: {errors.email && <span>{errors.email.message}</span>}"],
        "HIGH", 0.95, times_applied=65,
        context={"applies_to": ["React 18+"], "libraries": ["react-hook-form", "zod"]}
    ),

    # ── Flutter ────────────────────────────────────────────────────────────
    "fw_flutter_architecture": _learning(
        "PATTERN", "FLUTTER",
        "Flutter clean architecture: lib/{core,features,shared}. Each feature: {data,domain,presentation}. "
        "Data: repositories, data sources, models. Domain: entities, use cases, repository interfaces. "
        "Presentation: pages, widgets, state management (BLoC/Riverpod).",
        ["Structure: lib/features/auth/{data/{repos,sources,models}, domain/{entities,usecases,repos}, presentation/{pages,widgets,bloc}}",
         "Use case: class GetUser { final UserRepository repo; Future<User> call(String id) => repo.getUser(id); }",
         "Repository: abstract class UserRepository { Future<User> getUser(String id); }",
         "Dependency injection: Use get_it or riverpod for DI"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["Flutter 3+", "Dart 3+"]}
    ),
    "fw_flutter_navigation": _learning(
        "PATTERN", "FLUTTER",
        "Flutter navigation: Use go_router for declarative routing. Define routes with GoRouter. "
        "ShellRoute for persistent navigation (bottom nav bar). Redirect for auth guards. "
        "Use path parameters and query parameters for deep linking.",
        ["Router: final router = GoRouter(routes: [GoRoute(path: '/', builder: (ctx, state) => HomePage()), GoRoute(path: '/user/:id', builder: (ctx, state) => UserPage(id: state.pathParameters['id']!))])",
         "Shell: ShellRoute(builder: (ctx, state, child) => ScaffoldWithNav(child: child), routes: [...])",
         "Redirect: redirect: (ctx, state) { if (!isLoggedIn) return '/login'; return null; }",
         "Navigate: context.go('/user/123'); context.push('/settings');"],
        "HIGH", 0.94, times_applied=55,
        context={"applies_to": ["Flutter 3+"], "package": "go_router"}
    ),
    "fw_flutter_widgets": _learning(
        "PATTERN", "FLUTTER",
        "Flutter widget best practices: Prefer const constructors. Extract widgets into separate classes "
        "over helper methods. Use Builder pattern for context access. Keys for lists and animations. "
        "CustomPainter for complex drawings. Slivers for advanced scrolling.",
        ["Const: class MyWidget extends StatelessWidget { const MyWidget({super.key}); }",
         "Extract: class UserAvatar extends StatelessWidget {} // not Widget _buildAvatar()",
         "ListView: ListView.builder(itemCount: items.length, itemBuilder: (ctx, i) => ListTile(key: ValueKey(items[i].id), title: Text(items[i].name)))",
         "Sliver: CustomScrollView(slivers: [SliverAppBar(...), SliverList(...)])"],
        "HIGH", 0.95, times_applied=75,
        context={"applies_to": ["Flutter 3+"]}
    ),

    # ── Node.js / Express ──────────────────────────────────────────────────
    "fw_express_middleware": _learning(
        "PATTERN", "NODEJS",
        "Express middleware chain: app.use(cors()), app.use(helmet()), app.use(express.json()), "
        "app.use(rateLimit()), routes, app.use(errorHandler). Order matters. Custom middleware: "
        "(req, res, next) => { /* logic */ next(); }. Error middleware has 4 params: (err, req, res, next).",
        ["Auth: const auth = (req, res, next) => { const token = req.headers.authorization?.split(' ')[1]; if(!token) return res.status(401).json({error:'No token'}); try { req.user = jwt.verify(token, SECRET); next(); } catch { res.status(403).json({error:'Invalid token'}); } }",
         "Error: app.use((err, req, res, next) => { console.error(err); res.status(err.status||500).json({error:err.message}); })",
         "Rate limit: app.use(rateLimit({windowMs:15*60*1000, max:100}))",
         "Security: app.use(helmet()); app.use(cors({origin:ALLOWED_ORIGINS}));"],
        "HIGH", 0.96, times_applied=90,
        context={"applies_to": ["Express.js", "Node.js"]}
    ),
    "fw_express_structure": _learning(
        "PATTERN", "NODEJS",
        "Express project structure: src/{routes,controllers,services,models,middleware,utils,config}. "
        "Route files define endpoints. Controllers handle request/response. Services contain business logic. "
        "Models define data shapes. Keep routes thin — delegate to controllers → services.",
        ["Route: router.get('/', userController.list); router.post('/', validate(createSchema), userController.create);",
         "Controller: const list = async (req, res, next) => { try { const users = await userService.findAll(req.query); res.json(users); } catch(e) { next(e); } }",
         "Service: class UserService { async findAll(filters) { return UserModel.find(filters).lean(); } }",
         "Index: app.use('/api/v1/users', authMiddleware, userRoutes);"],
        "HIGH", 0.95, times_applied=75,
        context={"applies_to": ["Express.js", "Node.js"]}
    ),

    # ── FastAPI ────────────────────────────────────────────────────────────
    "fw_fastapi_structure": _learning(
        "PATTERN", "FASTAPI",
        "FastAPI project structure: app/{main.py,routers/,models/,schemas/,services/,core/,db/}. "
        "Use APIRouter for modular routes. Pydantic BaseModel for request/response schemas. "
        "Depends() for dependency injection. BackgroundTasks for async jobs. Lifespan for startup/shutdown.",
        ["Router: router = APIRouter(prefix='/users', tags=['users']); @router.get('/', response_model=list[UserOut])",
         "Schema: class UserCreate(BaseModel): name: str = Field(min_length=1); email: EmailStr",
         "Depends: async def get_db(): async with SessionLocal() as session: yield session",
         "Lifespan: @asynccontextmanager async def lifespan(app): await init_db(); yield; await close_db()"],
        "HIGH", 0.95, times_applied=55,
        context={"applies_to": ["FastAPI", "Python 3.9+"]}
    ),
    "fw_fastapi_auth": _learning(
        "PATTERN", "FASTAPI",
        "FastAPI auth: OAuth2PasswordBearer for JWT flow. Dependency injection for current user. "
        "HTTPBearer for API keys. Security scopes for role-based access. Password hashing with passlib/bcrypt.",
        ["Token: oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')",
         "Dependency: async def get_current_user(token: str = Depends(oauth2_scheme)): payload = jwt.decode(token, SECRET); return await get_user(payload['sub'])",
         "Protected: @router.get('/me') async def me(user: User = Depends(get_current_user)): return user",
         "Hash: pwd_context = CryptContext(schemes=['bcrypt']); hashed = pwd_context.hash(password)"],
        "CRITICAL", 0.95, times_applied=50,
        context={"applies_to": ["FastAPI"], "packages": ["python-jose", "passlib", "bcrypt"]}
    ),

    # ── Next.js ────────────────────────────────────────────────────────────
    "fw_nextjs_app_router": _learning(
        "PATTERN", "NEXTJS",
        "Next.js App Router (13+): app/ directory with page.tsx, layout.tsx, loading.tsx, error.tsx. "
        "Server Components by default — add 'use client' for client interactivity. "
        "Server Actions for mutations. Parallel routes with @folder. Route groups with (folder).",
        ["Page: app/users/[id]/page.tsx exports default async function UserPage({ params })",
         "Layout: app/layout.tsx — persistent layout wrapping all pages",
         "Server Action: 'use server'; async function createUser(formData: FormData) { await db.insert(...); revalidatePath('/users'); }",
         "Loading: app/users/loading.tsx — automatic Suspense boundary"],
        "HIGH", 0.95, times_applied=55,
        context={"applies_to": ["Next.js 13+", "React 18+"]}
    ),
    "fw_nextjs_data_fetching": _learning(
        "PATTERN", "NEXTJS",
        "Next.js data fetching: Server Components fetch directly (no useEffect). "
        "Use fetch() with cache/revalidate options. generateStaticParams for SSG. "
        "unstable_cache for function-level caching. revalidatePath/revalidateTag for on-demand ISR.",
        ["Server fetch: const users = await fetch(API_URL, { next: { revalidate: 60 } }).then(r => r.json())",
         "SSG: export async function generateStaticParams() { return posts.map(p => ({ slug: p.slug })); }",
         "Revalidate: revalidateTag('users') after mutation",
         "Client: Use TanStack Query for client-side data that needs frequent updates"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["Next.js 13+"]}
    ),

    # ── Django ─────────────────────────────────────────────────────────────
    "fw_django_rest_framework": _learning(
        "PATTERN", "DJANGO",
        "Django REST Framework: ModelSerializer for auto CRUD. ViewSet + Router for URL generation. "
        "Permission classes for access control. Pagination, filtering, throttling built-in. "
        "Use DRF serializers for validation — not Django forms in API views.",
        ["Serializer: class UserSerializer(serializers.ModelSerializer): class Meta: model = User; fields = '__all__'",
         "ViewSet: class UserViewSet(viewsets.ModelViewSet): queryset = User.objects.all(); serializer_class = UserSerializer; permission_classes = [IsAuthenticated]",
         "Router: router = DefaultRouter(); router.register('users', UserViewSet)",
         "Filter: filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]"],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["Django 4+", "DRF 3.14+"]}
    ),

    # ── NestJS ─────────────────────────────────────────────────────────────
    "fw_nestjs_modules": _learning(
        "PATTERN", "NESTJS",
        "NestJS architecture: Modules encapsulate features. Each module has controllers, providers (services), "
        "imports. Use @Injectable() for services. @Controller() for routes. Pipes for validation. "
        "Guards for auth. Interceptors for transform/cache.",
        ["Module: @Module({ controllers: [UserController], providers: [UserService], imports: [TypeOrmModule.forFeature([User])] }) export class UserModule {}",
         "Service: @Injectable() export class UserService { constructor(@InjectRepository(User) private repo: Repository<User>) {} }",
         "Controller: @Controller('users') export class UserController { @Get() findAll() { return this.userService.findAll(); } }",
         "Guard: @UseGuards(JwtAuthGuard) @Get('profile') getProfile(@Req() req) { return req.user; }"],
        "HIGH", 0.94, times_applied=45,
        context={"applies_to": ["NestJS", "TypeScript"]}
    ),
}

# ============================================================================
#  PATTERNS
# ============================================================================

FRAMEWORK_PATTERNS = {
    "pat_spring_rest_controller": _pattern(
        "Spring REST Controller", "SPRING_BOOT",
        "Complete REST controller with CRUD, validation, pagination, and error handling",
        "API layer in Spring Boot applications",
        "@RestController @RequestMapping(\"/api/v1/users\") @RequiredArgsConstructor public class UserController { private final UserService service; @GetMapping public Page<UserDTO> list(Pageable pageable) { return service.findAll(pageable); } @GetMapping(\"/{id}\") public UserDTO get(@PathVariable Long id) { return service.findById(id); } @PostMapping @ResponseStatus(CREATED) public UserDTO create(@Valid @RequestBody CreateUserDTO dto) { return service.create(dto); } @PutMapping(\"/{id}\") public UserDTO update(@PathVariable Long id, @Valid @RequestBody UpdateUserDTO dto) { return service.update(id, dto); } @DeleteMapping(\"/{id}\") @ResponseStatus(NO_CONTENT) public void delete(@PathVariable Long id) { service.delete(id); } }",
        "Spring Boot 3+", 0.97, times_used=130
    ),
    "pat_spring_exception_handler": _pattern(
        "Global Exception Handler", "SPRING_BOOT",
        "ControllerAdvice for centralized error handling with problem details",
        "Error handling across all Spring Boot controllers",
        "@ControllerAdvice public class GlobalExceptionHandler { @ExceptionHandler(EntityNotFoundException.class) public ProblemDetail handleNotFound(EntityNotFoundException e) { ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage()); pd.setTitle(\"Not Found\"); return pd; } @ExceptionHandler(MethodArgumentNotValidException.class) public ProblemDetail handleValidation(MethodArgumentNotValidException e) { ProblemDetail pd = ProblemDetail.forStatus(HttpStatus.BAD_REQUEST); pd.setTitle(\"Validation Failed\"); pd.setProperty(\"errors\", e.getFieldErrors().stream().map(f -> Map.of(\"field\",f.getField(),\"message\",f.getDefaultMessage())).toList()); return pd; } }",
        "Spring Boot 3+", 0.96, times_used=80
    ),
    "pat_react_page_component": _pattern(
        "React Page Component", "REACT",
        "Full page component with data fetching, loading/error states, and TypeScript",
        "Page-level components in React SPAs",
        "export default function UsersPage() { const { data: users, isLoading, error } = useQuery({ queryKey: ['users'], queryFn: fetchUsers }); if(isLoading) return <Skeleton count={5} />; if(error) return <ErrorAlert message={error.message} />; return (<div className='container'><h1>Users</h1><DataTable columns={columns} data={users} /><CreateUserDialog /></div>); }",
        "React 18+", 0.95, times_used=70
    ),
    "pat_flutter_screen": _pattern(
        "Flutter Screen Template", "FLUTTER",
        "Stateful screen with BLoC/Riverpod state, error handling, pull to refresh",
        "Feature screens in Flutter apps",
        "class UsersScreen extends ConsumerWidget { const UsersScreen({super.key}); @override Widget build(BuildContext context, WidgetRef ref) { final usersAsync = ref.watch(usersProvider); return Scaffold(appBar: AppBar(title: const Text('Users')), body: usersAsync.when(data: (users) => RefreshIndicator(onRefresh: () => ref.refresh(usersProvider.future), child: ListView.builder(itemCount: users.length, itemBuilder: (ctx, i) => UserTile(user: users[i]))), loading: () => const Center(child: CircularProgressIndicator()), error: (e, s) => ErrorWidget(message: e.toString(), onRetry: () => ref.invalidate(usersProvider)))); } }",
        "Flutter 3+", 0.94, times_used=55
    ),
    "pat_nextjs_server_action": _pattern(
        "Next.js Server Action", "NEXTJS",
        "Server action with validation, database mutation, and revalidation",
        "Form submissions and mutations in Next.js App Router",
        "'use server'; import { z } from 'zod'; import { revalidatePath } from 'next/cache'; const schema = z.object({ name: z.string().min(1), email: z.string().email() }); export async function createUser(formData: FormData) { const parsed = schema.safeParse(Object.fromEntries(formData)); if(!parsed.success) return { error: parsed.error.flatten() }; await db.user.create({ data: parsed.data }); revalidatePath('/users'); return { success: true }; }",
        "Next.js 14+", 0.94, times_used=40
    ),
}

# ============================================================================
#  CODE TEMPLATES
# ============================================================================

FRAMEWORK_TEMPLATES = {
    "tpl_spring_application_yml": _code_template(
        "Spring Boot application.yml", "YAML", "Spring Boot",
        "configuration",
        "server:\n  port: 8080\n  error:\n    include-message: always\nspring:\n  application:\n    name: supremeai\n  datasource:\n    url: jdbc:postgresql://localhost:5432/mydb\n    username: ${DB_USER}\n    password: ${DB_PASSWORD}\n  jpa:\n    hibernate:\n      ddl-auto: validate\n    open-in-view: false\n    properties:\n      hibernate:\n        format_sql: true\n  jackson:\n    default-property-inclusion: non_null\n    serialization:\n      write-dates-as-timestamps: false\nmanagement:\n  endpoints:\n    web:\n      exposure:\n        include: health,info,prometheus\nlogging:\n  level:\n    root: INFO\n    com.supremeai: DEBUG",
        "Production-ready Spring Boot configuration with security, JPA, Jackson, and Actuator settings",
        ["spring-boot", "configuration", "yaml", "production"]
    ),
    "tpl_react_app_layout": _code_template(
        "React App Layout", "TypeScript", "React",
        "layout",
        "import { Outlet } from 'react-router-dom';\nimport { Sidebar } from './Sidebar';\nimport { Header } from './Header';\nimport { Toaster } from '@/components/ui/toaster';\n\nexport function AppLayout() {\n  return (\n    <div className=\"flex h-screen\">\n      <Sidebar />\n      <div className=\"flex flex-1 flex-col\">\n        <Header />\n        <main className=\"flex-1 overflow-auto p-6\">\n          <Outlet />\n        </main>\n      </div>\n      <Toaster />\n    </div>\n  );\n}",
        "Standard app layout with sidebar, header, and content area using React Router outlet",
        ["react", "layout", "sidebar", "router"]
    ),
    "tpl_flutter_main": _code_template(
        "Flutter main.dart", "Dart", "Flutter",
        "entrypoint",
        "import 'package:flutter/material.dart';\nimport 'package:flutter_riverpod/flutter_riverpod.dart';\nimport 'router.dart';\nimport 'theme.dart';\n\nvoid main() {\n  WidgetsFlutterBinding.ensureInitialized();\n  runApp(const ProviderScope(child: MyApp()));\n}\n\nclass MyApp extends ConsumerWidget {\n  const MyApp({super.key});\n  @override\n  Widget build(BuildContext context, WidgetRef ref) {\n    final router = ref.watch(routerProvider);\n    return MaterialApp.router(\n      title: 'SupremeAI',\n      theme: appTheme,\n      darkTheme: appDarkTheme,\n      routerConfig: router,\n      debugShowCheckedModeBanner: false,\n    );\n  }\n}",
        "Flutter app entry point with Riverpod, theming, and go_router setup",
        ["flutter", "main", "riverpod", "router"]
    ),
    "tpl_dockerfile_spring": _code_template(
        "Spring Boot Dockerfile", "Dockerfile", "Spring Boot",
        "deployment",
        "FROM eclipse-temurin:21-jre-alpine AS runtime\nWORKDIR /app\nCOPY build/libs/*.jar app.jar\nEXPOSE 8080\nHEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost:8080/actuator/health || exit 1\nENTRYPOINT [\"java\", \"-XX:+UseContainerSupport\", \"-XX:MaxRAMPercentage=75.0\", \"-jar\", \"app.jar\"]",
        "Multi-stage Dockerfile for Spring Boot with health check and JVM tuning",
        ["docker", "spring-boot", "production", "jvm"]
    ),
    "tpl_express_server": _code_template(
        "Express Server Setup", "TypeScript", "Express",
        "entrypoint",
        "import express from 'express';\nimport cors from 'cors';\nimport helmet from 'helmet';\nimport { rateLimit } from 'express-rate-limit';\nimport { errorHandler } from './middleware/error';\nimport { userRoutes } from './routes/users';\n\nconst app = express();\napp.use(helmet());\napp.use(cors({ origin: process.env.ALLOWED_ORIGINS?.split(',') }));\napp.use(express.json({ limit: '10mb' }));\napp.use(rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }));\napp.use('/api/v1/users', userRoutes);\napp.use(errorHandler);\n\nconst PORT = process.env.PORT || 3000;\napp.listen(PORT, () => console.log(`Server running on port ${PORT}`));",
        "Express server with security middleware, rate limiting, and structured routes",
        ["express", "nodejs", "server", "security"]
    ),
    "tpl_fastapi_main": _code_template(
        "FastAPI Main", "Python", "FastAPI",
        "entrypoint",
        "from contextlib import asynccontextmanager\nfrom fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom app.routers import users, auth\nfrom app.db import init_db, close_db\n\n@asynccontextmanager\nasync def lifespan(app: FastAPI):\n    await init_db()\n    yield\n    await close_db()\n\napp = FastAPI(title='SupremeAI API', version='1.0.0', lifespan=lifespan)\napp.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])\napp.include_router(auth.router, prefix='/api/v1/auth', tags=['auth'])\napp.include_router(users.router, prefix='/api/v1/users', tags=['users'])\n\n@app.get('/health')\nasync def health(): return {'status': 'ok'}",
        "FastAPI application with lifespan, CORS, and modular routers",
        ["fastapi", "python", "api", "async"]
    ),
}
