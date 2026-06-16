"""
Part 9: Error Solutions Encyclopedia
Covers: Common errors across Java, Python, JS, Dart, Docker, K8s, Git, build tools
~80 error-fix pairs
"""
from seed_data.helpers import _error_fix

ERROR_FIXES = {

    # ── Java / Spring Boot Errors ──────────────────────────────────────────
    "err_java_npe": _error_fix(
        "java.lang.NullPointerException",
        "Accessing method or field on null reference",
        "Use Optional<T> for nullable returns. Add null checks. Enable @NonNull annotations. Use Objects.requireNonNull() at boundaries.",
        "Java", "Java", 0.98, occurrences=500, ai_fixed="Claude"
    ),
    "err_java_class_not_found": _error_fix(
        "java.lang.ClassNotFoundException / NoClassDefFoundError",
        "Missing dependency or wrong classpath configuration",
        "Check build.gradle/pom.xml for missing dependency. Run ./gradlew dependencies to check resolution. Clean and rebuild: ./gradlew clean build.",
        "Java", "Gradle/Maven", 0.95, occurrences=120
    ),
    "err_spring_bean_not_found": _error_fix(
        "NoSuchBeanDefinitionException: No qualifying bean of type",
        "Missing @Component/@Service/@Repository annotation or component scan not covering package",
        "Add @Service/@Component to the class. Check @SpringBootApplication is in parent package. Add @ComponentScan if needed. Check @Configuration imports.",
        "Java", "Spring Boot", 0.96, occurrences=200
    ),
    "err_spring_circular_dep": _error_fix(
        "BeanCurrentlyInCreationException: Requested bean is currently in creation: circular reference",
        "Two or more beans depend on each other creating a cycle",
        "Use @Lazy on one dependency. Refactor to break cycle with events or a mediator. Use setter injection instead of constructor injection for one side.",
        "Java", "Spring Boot", 0.94, occurrences=80
    ),
    "err_spring_404": _error_fix(
        "Whitelabel Error Page - 404 Not Found for REST endpoint",
        "Controller not scanned, wrong @RequestMapping path, or missing @RestController",
        "Verify @RestController (not @Controller for REST). Check @RequestMapping prefix matches URL. Ensure controller package is under @SpringBootApplication package.",
        "Java", "Spring Boot", 0.97, occurrences=150
    ),
    "err_jpa_lazy_init": _error_fix(
        "LazyInitializationException: could not initialize proxy - no Session",
        "Accessing lazy-loaded relation outside Hibernate session/transaction",
        "Use JOIN FETCH in JPQL query. Use @EntityGraph on repository method. Use DTO projection instead of entity. Set spring.jpa.open-in-view=false and fetch eagerly where needed.",
        "Java", "JPA/Hibernate", 0.95, occurrences=130
    ),
    "err_jpa_detached_entity": _error_fix(
        "PersistentObjectException: detached entity passed to persist",
        "Trying to persist an entity that already has an ID or was previously managed",
        "Use merge() instead of persist() for existing entities. Use save() which handles both. Remove manual ID setting if using @GeneratedValue.",
        "Java", "JPA/Hibernate", 0.94, occurrences=70
    ),
    "err_spring_cors": _error_fix(
        "CORS: Response to preflight request doesn't pass access control check",
        "Missing or incorrect CORS configuration in Spring Security",
        "Add CORS config in SecurityFilterChain: http.cors(c -> c.configurationSource(corsConfig())). Define CorsConfiguration with allowed origins, methods, headers. Ensure OPTIONS is permitted.",
        "Java", "Spring Boot", 0.97, occurrences=180
    ),
    "err_gradle_version_conflict": _error_fix(
        "Could not resolve all files for configuration ':classpath'. Could not resolve com.android.tools.build:gradle",
        "Gradle version incompatible with plugin or JDK version",
        "Update gradle wrapper: ./gradlew wrapper --gradle-version=8.5. Check JDK compatibility. Update plugin version in build.gradle.kts. Check distributionUrl in gradle-wrapper.properties.",
        "Kotlin/Groovy", "Gradle", 0.94, occurrences=90
    ),
    "err_java_oom": _error_fix(
        "java.lang.OutOfMemoryError: Java heap space",
        "JVM heap exceeded due to large data processing, memory leaks, or insufficient allocation",
        "Increase heap: -Xmx512m. Check for memory leaks with profiler (VisualVM, JFR). Use streaming instead of loading all data. Check for unclosed resources (connections, streams).",
        "Java", "JVM", 0.93, occurrences=60
    ),

    # ── Python Errors ──────────────────────────────────────────────────────
    "err_python_import": _error_fix(
        "ModuleNotFoundError: No module named 'xxx'",
        "Package not installed or wrong virtual environment",
        "Install: pip install xxx. Check venv is activated: which python. Add to requirements.txt. Check for typos in import. Verify __init__.py exists in package directories.",
        "Python", "Python", 0.97, occurrences=300
    ),
    "err_python_indentation": _error_fix(
        "IndentationError: unexpected indent / unindent does not match",
        "Mixing tabs and spaces or inconsistent indentation",
        "Use spaces only (4 spaces per level). Configure editor: insert spaces, tab size 4. Run: python -tt script.py to detect. autopep8 or black for auto-formatting.",
        "Python", "Python", 0.98, occurrences=200
    ),
    "err_python_type_error": _error_fix(
        "TypeError: can only concatenate str (not \"int\") to str",
        "Mixing types in operations without conversion",
        "Use f-strings: f'Count: {count}'. Use str() for explicit conversion. Use type hints to catch at dev time. Enable mypy strict mode.",
        "Python", "Python", 0.97, occurrences=180
    ),
    "err_python_async": _error_fix(
        "RuntimeError: This event loop is already running / coroutine was never awaited",
        "Missing await keyword or nested event loops",
        "Add 'await' before async function calls. Don't use asyncio.run() inside an already running loop. Use nest_asyncio if needed in Jupyter. Check async def uses await for all async calls.",
        "Python", "asyncio", 0.94, occurrences=80
    ),
    "err_fastapi_422": _error_fix(
        "422 Unprocessable Entity on FastAPI endpoint",
        "Request body doesn't match Pydantic model validation",
        "Check request Content-Type is application/json. Verify request body matches Pydantic model fields exactly. Check field types and constraints. Add validation error handler for readable messages.",
        "Python", "FastAPI", 0.96, occurrences=120
    ),

    # ── JavaScript/TypeScript Errors ───────────────────────────────────────
    "err_js_undefined": _error_fix(
        "TypeError: Cannot read properties of undefined (reading 'xxx')",
        "Accessing property on undefined variable, often from async data or missing null check",
        "Use optional chaining: obj?.property. Check data is loaded before accessing. Initialize state with default values. Use TypeScript strict mode for compile-time null checks.",
        "JavaScript", "JavaScript", 0.97, occurrences=400
    ),
    "err_js_cors_fetch": _error_fix(
        "TypeError: Failed to fetch / CORS error in browser console",
        "Backend doesn't return proper CORS headers or URL is wrong",
        "Configure CORS on backend (allow origin, methods, headers). Check URL is correct (http vs https, port). Use proxy in development (Vite proxy, CRA proxy). Check network tab for actual error.",
        "JavaScript", "Browser/Fetch", 0.96, occurrences=250
    ),
    "err_ts_type_mismatch": _error_fix(
        "Type 'X' is not assignable to type 'Y'",
        "TypeScript type incompatibility between assignment and declaration",
        "Check types match. Use type assertion with 'as' only when certain. Use utility types: Partial<T>, Pick<T>, Omit<T>. Add missing fields or update type definition.",
        "TypeScript", "TypeScript", 0.95, occurrences=300
    ),
    "err_react_invalid_hook": _error_fix(
        "Error: Invalid hook call. Hooks can only be called inside the body of a function component",
        "Hook called outside component, in conditional, or duplicate React versions",
        "Only call hooks at top level of function components. Don't call in conditions/loops. Check for duplicate React in node_modules: npm ls react. Ensure component name starts with uppercase.",
        "TypeScript", "React", 0.96, occurrences=120
    ),
    "err_react_key_warning": _error_fix(
        "Warning: Each child in a list should have a unique 'key' prop",
        "Missing or non-unique key prop in list rendering",
        "Add unique key prop: items.map(item => <Item key={item.id} />). Use stable IDs, never array index for dynamic lists. Key must be unique among siblings.",
        "TypeScript", "React", 0.98, occurrences=200
    ),
    "err_react_too_many_renders": _error_fix(
        "Error: Too many re-renders. React limits the number of renders to prevent an infinite loop",
        "setState called during render or in useEffect without proper dependency array",
        "Don't call setState directly in component body. Use useEffect with proper deps array. Use callback form: onClick={() => setCount(c => c+1)} not onClick={setCount(count+1)}.",
        "TypeScript", "React", 0.96, occurrences=150
    ),
    "err_nextjs_hydration": _error_fix(
        "Error: Hydration failed because the initial UI does not match what was rendered on the server",
        "Server and client render different HTML, often due to browser-only APIs or date/time",
        "Use useEffect for browser-only code. Suppress with suppressHydrationWarning for intentional differences. Use dynamic import with ssr:false for client-only components.",
        "TypeScript", "Next.js", 0.94, occurrences=80
    ),
    "err_npm_peer_deps": _error_fix(
        "npm ERR! Could not resolve dependency: peer dep conflict",
        "Conflicting peer dependency versions between packages",
        "Try: npm install --legacy-peer-deps. Or: update conflicting packages. Check which package requires the peer dep: npm explain <package>. Use overrides in package.json if needed.",
        "JavaScript", "npm", 0.94, occurrences=130
    ),
    "err_node_esm_cjs": _error_fix(
        "ERR_REQUIRE_ESM: Must use import to load ES Module / Cannot use import statement outside a module",
        "Mixing CommonJS and ES Module syntax",
        "Set 'type': 'module' in package.json for ESM. Use .mjs extension for ESM files. Use .cjs for CommonJS. Use dynamic import() for importing ESM in CJS.",
        "JavaScript", "Node.js", 0.94, occurrences=100
    ),

    # ── Dart / Flutter Errors ──────────────────────────────────────────────
    "err_dart_null_check": _error_fix(
        "Null check operator used on a null value",
        "Using ! operator on a null value at runtime",
        "Replace ! with proper null check: if (value != null). Use ?? for default values. Use ?. for optional chaining. Check API response can be null.",
        "Dart", "Flutter", 0.96, occurrences=180
    ),
    "err_flutter_overflow": _error_fix(
        "A RenderFlex overflowed by N pixels on the right/bottom",
        "Widget exceeds parent container bounds",
        "Wrap in SingleChildScrollView for scrolling. Use Flexible/Expanded in Row/Column. Set overflow: TextOverflow.ellipsis for text. Use ConstrainedBox or SizedBox for explicit bounds.",
        "Dart", "Flutter", 0.97, occurrences=200
    ),
    "err_flutter_state_disposed": _error_fix(
        "setState() called after dispose()",
        "Async operation completes after widget is removed from tree",
        "Check mounted before setState: if(mounted) setState(() {}). Cancel subscriptions in dispose(). Use CancelableOperation. With Riverpod: ref.onDispose() to cancel.",
        "Dart", "Flutter", 0.96, occurrences=120
    ),
    "err_flutter_gradle_build": _error_fix(
        "Execution failed for task ':app:compileDebugKotlin' / Flutter build failed",
        "Gradle/Kotlin version mismatch or corrupted build cache",
        "Clean build: flutter clean && flutter pub get && cd android && ./gradlew clean && cd .. && flutter build. Update Kotlin version in android/build.gradle. Check minSdkVersion.",
        "Dart", "Flutter/Android", 0.94, occurrences=100
    ),
    "err_flutter_cocoapods": _error_fix(
        "CocoaPods could not find compatible versions for pod / CDN: trunk URL couldn't be downloaded",
        "iOS dependencies conflict or CocoaPods cache issue",
        "Clean: cd ios && pod deintegrate && pod cache clean --all && pod install. Update: pod repo update. Delete Podfile.lock and reinstall. Check minimum iOS version.",
        "Dart", "Flutter/iOS", 0.93, occurrences=90
    ),

    # ── Docker Errors ──────────────────────────────────────────────────────
    "err_docker_port_in_use": _error_fix(
        "Bind for 0.0.0.0:8080 failed: port is already allocated",
        "Another process is using the port",
        "Find process: lsof -i :8080 (Linux/Mac) or netstat -ano | findstr :8080 (Windows). Kill process or use different port: -p 8081:8080.",
        "Dockerfile", "Docker", 0.97, occurrences=150
    ),
    "err_docker_build_cache": _error_fix(
        "Docker build not picking up changes / using cached layer",
        "Docker layer caching serving stale layers",
        "Use --no-cache for full rebuild. Restructure Dockerfile: COPY requirements first, then source code. Use .dockerignore to exclude node_modules, .git.",
        "Dockerfile", "Docker", 0.95, occurrences=80
    ),
    "err_docker_oom_killed": _error_fix(
        "Container killed: OOMKilled / Exited (137)",
        "Container exceeded memory limit",
        "Increase memory limit: docker run -m 512m. For JVM: set -XX:MaxRAMPercentage=75.0. Check for memory leaks. Use multi-stage build to reduce image size.",
        "Dockerfile", "Docker", 0.94, occurrences=60
    ),
    "err_docker_network": _error_fix(
        "Could not resolve host / Connection refused between containers",
        "Containers not on same Docker network or using wrong hostname",
        "Use service name as hostname in Docker Compose (not localhost). Ensure services are on same network. Check container is actually running: docker ps. Use depends_on with healthcheck.",
        "YAML", "Docker Compose", 0.96, occurrences=120
    ),

    # ── Kubernetes Errors ──────────────────────────────────────────────────
    "err_k8s_crashloopbackoff": _error_fix(
        "Pod in CrashLoopBackOff state",
        "Container crashes on startup repeatedly",
        "Check logs: kubectl logs <pod> --previous. Check: wrong command, missing env vars, health check failing too fast. Increase initialDelaySeconds for liveness probe. Check resource limits.",
        "YAML", "Kubernetes", 0.95, occurrences=100
    ),
    "err_k8s_imagepullbackoff": _error_fix(
        "Pod in ImagePullBackOff state",
        "Cannot pull container image from registry",
        "Check image name and tag exist. Verify registry credentials: kubectl create secret docker-registry. Check network access to registry. Use kubectl describe pod for details.",
        "YAML", "Kubernetes", 0.96, occurrences=80
    ),
    "err_k8s_pending": _error_fix(
        "Pod stuck in Pending state",
        "Insufficient cluster resources or scheduling constraints",
        "Check: kubectl describe pod <name> for events. Verify node resources: kubectl describe node. Check PVC is bound. Check nodeSelector/tolerations match available nodes.",
        "YAML", "Kubernetes", 0.94, occurrences=70
    ),

    # ── Git Errors ─────────────────────────────────────────────────────────
    "err_git_merge_conflict": _error_fix(
        "CONFLICT (content): Merge conflict in <file>",
        "Both branches modified the same lines",
        "Open file, look for <<<<<<< markers. Choose correct version or combine. Stage resolved files: git add <file>. Continue: git merge --continue or git rebase --continue.",
        "Git", "Git", 0.97, occurrences=300
    ),
    "err_git_push_rejected": _error_fix(
        "error: failed to push some refs to origin. Updates were rejected because the remote contains work",
        "Remote has commits not in local branch",
        "Pull first: git pull --rebase origin main. Resolve any conflicts. Then push. NEVER force push to shared branches unless you know what you're doing.",
        "Git", "Git", 0.97, occurrences=200
    ),
    "err_git_detached_head": _error_fix(
        "You are in 'detached HEAD' state",
        "Checked out a specific commit or tag instead of a branch",
        "Create branch from current state: git checkout -b new-branch. Or go back: git checkout main. Commits in detached HEAD are lost unless you create a branch.",
        "Git", "Git", 0.96, occurrences=80
    ),
    "err_git_large_file": _error_fix(
        "remote: error: File xxx is 100 MB+ and exceeds GitHub's file size limit",
        "Trying to push a file larger than GitHub's 100MB limit",
        "Add to .gitignore. Remove from history: git filter-branch or BFG Repo Cleaner. Use Git LFS for large files: git lfs track '*.zip'.",
        "Git", "GitHub", 0.95, occurrences=50
    ),

    # ── Build Tool Errors ──────────────────────────────────────────────────
    "err_gradle_daemon": _error_fix(
        "Gradle build daemon disappeared unexpectedly / Could not connect to Gradle daemon",
        "Gradle daemon crashed, usually due to memory or JDK issues",
        "Stop daemons: ./gradlew --stop. Increase memory: org.gradle.jvmargs=-Xmx2g in gradle.properties. Check JDK version compatibility. Delete .gradle cache.",
        "Kotlin", "Gradle", 0.94, occurrences=70
    ),
    "err_webpack_module_not_found": _error_fix(
        "Module not found: Can't resolve './Component' in '/src'",
        "Missing file, wrong path, or missing file extension in import",
        "Check file exists at the exact path. Check case sensitivity (Linux is case-sensitive). Add extensions to resolve: resolve.extensions in webpack config. Check tsconfig paths.",
        "JavaScript", "Webpack/Vite", 0.95, occurrences=120
    ),
    "err_vite_hmr": _error_fix(
        "[vite] hot module replacement (HMR) disconnected / WebSocket connection failed",
        "Vite dev server WebSocket can't connect, often proxy or network issue",
        "Check server.hmr config in vite.config. Set server.hmr.host explicitly. If behind proxy: configure WebSocket proxy. Check firewall/antivirus not blocking.",
        "TypeScript", "Vite", 0.93, occurrences=50
    ),

    # ── Firebase Errors ────────────────────────────────────────────────────
    "err_firebase_permission_denied": _error_fix(
        "FirebaseError: Missing or insufficient permissions",
        "Firestore/RTDB security rules blocking the operation",
        "Check security rules match the operation (read/write/create/update/delete). Verify user is authenticated. Check rule conditions. Test in Firebase emulator with debug logging.",
        "JavaScript", "Firebase", 0.97, occurrences=200
    ),
    "err_firebase_index": _error_fix(
        "FirebaseError: The query requires an index. Create it at: https://...",
        "Composite index needed for the Firestore query",
        "Click the link in the error to auto-create the index. Or add to firestore.indexes.json. Index creation takes a few minutes. Add indexes proactively for common query patterns.",
        "JavaScript", "Firebase Firestore", 0.98, occurrences=150
    ),
    "err_firebase_auth": _error_fix(
        "FirebaseError: auth/user-not-found or auth/wrong-password",
        "User doesn't exist or password is incorrect",
        "Show generic error to user: 'Invalid email or password' (don't reveal which is wrong). Check email format. Implement rate limiting on auth endpoints. Check Auth provider is enabled.",
        "JavaScript", "Firebase Auth", 0.96, occurrences=100
    ),

    # ── Cloud / Deployment Errors ──────────────────────────────────────────
    "err_cloud_run_startup": _error_fix(
        "Cloud Run: Container failed to start. Failed to start and then listen on the port defined by the PORT environment variable",
        "Container not listening on $PORT or taking too long to start",
        "Read PORT from env: int port = Integer.parseInt(System.getenv().getOrDefault(\"PORT\", \"8080\")). Reduce startup time. Increase startup timeout in Cloud Run settings. Check for missing env vars.",
        "Java", "Cloud Run", 0.96, occurrences=80
    ),
    "err_gcp_permission": _error_fix(
        "403 Forbidden: The caller does not have permission / IAM permission denied",
        "Service account missing required IAM role",
        "Check required roles in GCP docs. Add role: gcloud projects add-iam-policy-binding PROJECT --member=serviceAccount:SA --role=roles/xxx. Check correct service account is being used.",
        "Shell", "GCP", 0.95, occurrences=100
    ),
    "err_ssl_cert": _error_fix(
        "SSL: CERTIFICATE_VERIFY_FAILED / unable to verify the first certificate",
        "SSL certificate issue: expired, self-signed, or missing intermediate cert",
        "Check cert expiry: openssl s_client -connect host:443. Renew if expired. Add intermediate certs to chain. For dev only: disable verify (NEVER in production).",
        "Shell", "SSL/TLS", 0.94, occurrences=70
    ),
}
