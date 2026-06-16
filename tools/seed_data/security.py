"""
Part 5: Security Knowledge
Covers: OWASP Top 10, JWT, OAuth2, encryption, input validation, CORS, CSP, secrets management
~25 learnings + ~20 best practices = 45 documents
"""
from seed_data.helpers import _learning, _best_practice

SECURITY_LEARNINGS = {

    # ── OWASP Top 10 ──────────────────────────────────────────────────────
    "sec_sql_injection": _learning(
        "PATTERN", "SECURITY",
        "SQL Injection (OWASP A03): Never concatenate user input into SQL. Always use parameterized "
        "queries / prepared statements. ORMs (JPA, SQLAlchemy, Prisma) are safe by default. "
        "Validate and sanitize input at controller boundary.",
        ["Java: PreparedStatement ps = conn.prepareStatement(\"SELECT * FROM users WHERE email = ?\"); ps.setString(1, email);",
         "JPA: @Query(\"SELECT u FROM User u WHERE u.email = :email\") User find(@Param(\"email\") String email);",
         "Python: cursor.execute(\"SELECT * FROM users WHERE email = %s\", (email,))",
         "NEVER: \"SELECT * FROM users WHERE email = '\" + email + \"'\""],
        "CRITICAL", 0.99, times_applied=200,
        context={"owasp": "A03:2021 Injection", "applies_to": ["ALL"]}
    ),
    "sec_xss": _learning(
        "PATTERN", "SECURITY",
        "Cross-Site Scripting (OWASP A03): Encode output, not just input. React auto-escapes JSX. "
        "Danger: dangerouslySetInnerHTML, v-html, [innerHTML]. Use Content-Security-Policy headers. "
        "DOMPurify for sanitizing HTML when needed.",
        ["React: JSX auto-escapes: <p>{userInput}</p> is safe",
         "Danger: <div dangerouslySetInnerHTML={{__html: userInput}} /> — NEVER with untrusted data",
         "Sanitize: const clean = DOMPurify.sanitize(dirtyHtml);",
         "CSP header: Content-Security-Policy: default-src 'self'; script-src 'self'"],
        "CRITICAL", 0.98, times_applied=150,
        context={"owasp": "A03:2021 Injection", "applies_to": ["React", "Angular", "Vue", "HTML"]}
    ),
    "sec_broken_auth": _learning(
        "PATTERN", "SECURITY",
        "Broken Authentication (OWASP A07): Use bcrypt/argon2 for password hashing (NEVER MD5/SHA). "
        "JWT: short expiry (15m access, 7d refresh). HttpOnly cookies for tokens. "
        "Rate limit login attempts. Implement account lockout after N failures.",
        ["Hash: BCryptPasswordEncoder encoder; String hash = encoder.encode(password);",
         "JWT: access token 15min, refresh token 7d, rotate refresh on use",
         "Cookie: Set-Cookie: token=xxx; HttpOnly; Secure; SameSite=Strict; Path=/",
         "Rate limit: Max 5 login attempts per 15 minutes per IP/account"],
        "CRITICAL", 0.98, times_applied=130,
        context={"owasp": "A07:2021 Identification and Authentication Failures", "applies_to": ["ALL"]}
    ),
    "sec_broken_access_control": _learning(
        "PATTERN", "SECURITY",
        "Broken Access Control (OWASP A01): Check authorization on every request. Never rely on "
        "client-side checks. IDOR: verify resource belongs to requesting user. "
        "Deny by default. Use role-based (RBAC) or attribute-based (ABAC) access control.",
        ["IDOR check: if (!order.getUserId().equals(currentUser.getId())) throw new ForbiddenException();",
         "Spring: @PreAuthorize(\"#userId == authentication.principal.id or hasRole('ADMIN')\")",
         "Default deny: .authorizeHttpRequests(a -> a.anyRequest().authenticated())",
         "Test: Try accessing /api/users/2 as user 1 — should get 403"],
        "CRITICAL", 0.98, times_applied=140,
        context={"owasp": "A01:2021 Broken Access Control", "applies_to": ["ALL"]}
    ),
    "sec_security_misconfiguration": _learning(
        "PATTERN", "SECURITY",
        "Security Misconfiguration (OWASP A05): Disable debug in production. Remove default credentials. "
        "Set security headers (HSTS, CSP, X-Frame-Options). Disable directory listing. "
        "Keep dependencies updated. Use security scanners (OWASP ZAP, Snyk).",
        ["Headers: Strict-Transport-Security: max-age=31536000; includeSubDomains",
         "Spring: server.error.include-stacktrace=never in production",
         "ENV: Never commit secrets — use environment variables or vault",
         "Scan: npm audit, ./gradlew dependencyCheckAnalyze, snyk test"],
        "HIGH", 0.96, times_applied=80,
        context={"owasp": "A05:2021 Security Misconfiguration", "applies_to": ["ALL"]}
    ),
    "sec_sensitive_data": _learning(
        "PATTERN", "SECURITY",
        "Sensitive Data Exposure (OWASP A02): Encrypt data at rest and in transit (TLS). "
        "Never log passwords/tokens/PII. Mask sensitive fields in API responses. "
        "Use KMS for key management. Encrypt database columns for PII.",
        ["TLS: Force HTTPS everywhere — redirect HTTP to HTTPS",
         "Logging: NEVER log.info(\"password: {}\", password); — use log.info(\"login attempt for user: {}\", username);",
         "API: Exclude sensitive fields: @JsonIgnore private String password;",
         "DB: Encrypt PII columns: AES-256 for SSN, credit cards"],
        "CRITICAL", 0.97, times_applied=100,
        context={"owasp": "A02:2021 Cryptographic Failures", "applies_to": ["ALL"]}
    ),
    "sec_ssrf": _learning(
        "PATTERN", "SECURITY",
        "Server-Side Request Forgery (OWASP A10): Validate and whitelist URLs before server-side fetching. "
        "Block internal IPs (127.0.0.1, 10.x, 192.168.x, 169.254.x). "
        "Don't allow user-controlled URLs for server-side requests without validation.",
        ["Whitelist: Set<String> ALLOWED_HOSTS = Set.of(\"api.github.com\", \"api.stripe.com\");",
         "Block internal: if (InetAddress.getByName(host).isSiteLocalAddress()) throw new SecurityException();",
         "Validate: URL url = new URL(userInput); if (!ALLOWED_HOSTS.contains(url.getHost())) reject;",
         "Use: DNS rebinding protection — resolve hostname, check IP, then fetch"],
        "HIGH", 0.95, times_applied=40,
        context={"owasp": "A10:2021 SSRF", "applies_to": ["Java", "Node.js", "Python"]}
    ),

    # ── JWT & OAuth2 ──────────────────────────────────────────────────────
    "sec_jwt_best_practices": _learning(
        "PATTERN", "SECURITY",
        "JWT best practices: Use RS256 (asymmetric) over HS256 for distributed systems. "
        "Short-lived access tokens (15min). Refresh tokens in HttpOnly cookies. "
        "Include: sub (user ID), exp, iat, iss, aud. Never store sensitive data in JWT payload.",
        ["Create: Jwts.builder().subject(userId).issuedAt(now).expiration(now.plusMinutes(15)).signWith(privateKey).compact()",
         "Verify: Jwts.parser().verifyWith(publicKey).requireIssuer(\"supremeai\").build().parseSignedClaims(token)",
         "Refresh flow: access token expired → send refresh token → get new access + rotate refresh",
         "Revocation: Use token blacklist (Redis) or short expiry + refresh rotation"],
        "CRITICAL", 0.97, times_applied=90,
        context={"applies_to": ["ALL"], "algorithm": "RS256 preferred"}
    ),
    "sec_oauth2_flows": _learning(
        "PATTERN", "SECURITY",
        "OAuth2 flows: Authorization Code + PKCE for web/mobile apps. Client Credentials for "
        "service-to-service. Never use Implicit flow (deprecated). Use state parameter to prevent CSRF. "
        "Store tokens securely — HttpOnly cookies for web, secure storage for mobile.",
        ["Auth Code + PKCE: Generate code_verifier → hash to code_challenge → redirect to /authorize → exchange code for tokens",
         "Client Credentials: POST /token with client_id + client_secret → get access token",
         "State: Generate random state, verify on callback to prevent CSRF",
         "Scopes: Request minimal scopes needed: openid profile email"],
        "HIGH", 0.95, times_applied=50,
        context={"applies_to": ["ALL"], "standard": "OAuth 2.1"}
    ),

    # ── Input Validation ──────────────────────────────────────────────────
    "sec_input_validation": _learning(
        "PATTERN", "SECURITY",
        "Input validation: Validate at system boundaries (controllers). Whitelist over blacklist. "
        "Validate type, length, range, format. Use framework validators (@Valid, Pydantic, Zod). "
        "Sanitize for the output context (HTML, SQL, shell).",
        ["Java: @NotBlank @Size(max=100) @Email String email; — validate at DTO level",
         "Python: class UserCreate(BaseModel): email: EmailStr; name: str = Field(min_length=1, max_length=100)",
         "TypeScript: const schema = z.object({ email: z.string().email(), name: z.string().min(1).max(100) })",
         "Branch name: if (!name.matches(\"^[a-zA-Z0-9_/-]+$\")) throw new InvalidInputException();"],
        "CRITICAL", 0.98, times_applied=160,
        context={"applies_to": ["ALL"], "principle": "Never trust client input"}
    ),
    "sec_command_injection": _learning(
        "PATTERN", "SECURITY",
        "Command Injection: Never pass user input to shell commands via string concatenation. "
        "Use array args for ProcessBuilder (Java), subprocess (Python). Validate inputs against whitelist. "
        "Avoid Runtime.exec(String) — use Runtime.exec(String[]).",
        ["Java SAFE: new ProcessBuilder(\"git\", \"checkout\", branchName).start() — array args",
         "Java UNSAFE: Runtime.getRuntime().exec(\"git checkout \" + branchName) — string concat!",
         "Python SAFE: subprocess.run([\"git\", \"checkout\", branch], shell=False)",
         "Python UNSAFE: os.system(f\"git checkout {branch}\") — shell injection!"],
        "CRITICAL", 0.99, times_applied=80,
        context={"applies_to": ["Java", "Python", "Node.js"], "supremeai": "Critical for GitService"}
    ),

    # ── CORS & Headers ────────────────────────────────────────────────────
    "sec_cors": _learning(
        "PATTERN", "SECURITY",
        "CORS: Allow only specific origins, not '*' in production with credentials. "
        "Set allowed methods and headers explicitly. Preflight caching with max-age. "
        "Credentials: Access-Control-Allow-Credentials: true requires specific origin (not *).",
        ["Spring: @Bean CorsConfigurationSource corsConfig() { config.setAllowedOrigins(List.of(\"https://app.supremeai.com\")); config.setAllowedMethods(List.of(\"GET\",\"POST\",\"PUT\",\"DELETE\")); config.setAllowCredentials(true); }",
         "Express: cors({ origin: ['https://app.supremeai.com'], credentials: true })",
         "NEVER in production: Access-Control-Allow-Origin: * with credentials",
         "Preflight: Access-Control-Max-Age: 3600 to cache OPTIONS responses"],
        "HIGH", 0.96, times_applied=70,
        context={"applies_to": ["ALL"]}
    ),
    "sec_secrets_management": _learning(
        "PATTERN", "SECURITY",
        "Secrets management: Never commit secrets to git. Use environment variables for simple setups. "
        "HashiCorp Vault or cloud KMS for production. .env files in .gitignore. "
        "Rotate secrets regularly. Use different secrets per environment.",
        ["Env: String token = System.getenv(\"GITHUB_TOKEN\"); if (token == null) throw new IllegalStateException(\"GITHUB_TOKEN not set\");",
         "Spring: @Value(\"${app.jwt-secret}\") — from env or vault",
         ".gitignore: .env, *.key, *.pem, secrets.yml, credentials.json",
         "Rotation: Automate secret rotation with cloud provider (GCP Secret Manager, AWS Secrets Manager)"],
        "CRITICAL", 0.97, times_applied=110,
        context={"applies_to": ["ALL"], "supremeai": "GITHUB_TOKEN, SUPREMEAI_SETUP_TOKEN must be env vars"}
    ),
}

# ============================================================================
#  BEST PRACTICES
# ============================================================================

SECURITY_PRACTICES = {
    "bp_password_hashing": _best_practice(
        "Password Hashing", "AUTHENTICATION",
        "Always hash passwords with bcrypt, scrypt, or Argon2. Never store plaintext or use MD5/SHA.",
        ["Use BCryptPasswordEncoder (Spring) with strength 12+",
         "Use passlib with bcrypt scheme (Python)",
         "Use bcrypt package (Node.js) with salt rounds 12",
         "Store only the hash, never the plaintext"],
        ["Use MD5 or SHA-1 for password hashing",
         "Store passwords in plaintext",
         "Use encryption instead of hashing for passwords",
         "Roll your own hashing algorithm"],
        "CRITICAL", ["Java", "Python", "Node.js", "ALL"]
    ),
    "bp_api_security": _best_practice(
        "API Security Checklist", "API",
        "Comprehensive API security: authentication, rate limiting, input validation, HTTPS, logging.",
        ["Require authentication on all non-public endpoints",
         "Rate limit all endpoints (100 req/15min per user)",
         "Validate all input with framework validators",
         "Use HTTPS everywhere — redirect HTTP",
         "Log security events (failed logins, permission denials)",
         "Return minimal error details in production"],
        ["Expose internal errors to clients",
         "Use API keys as sole authentication",
         "Allow unlimited request rates",
         "Return stack traces in production errors",
         "Log sensitive data (passwords, tokens, PII)"],
        "CRITICAL", ["Spring Boot", "Express", "FastAPI", "ALL"]
    ),
    "bp_dependency_security": _best_practice(
        "Dependency Security", "SUPPLY_CHAIN",
        "Keep dependencies updated. Scan for vulnerabilities. Use lock files. Verify checksums.",
        ["Run npm audit / pip audit / gradle dependencyCheckAnalyze regularly",
         "Enable Dependabot or Renovate for auto-updates",
         "Use lock files (package-lock.json, Pipfile.lock, gradle.lockfile)",
         "Pin major versions, allow patch updates"],
        ["Ignore security audit warnings",
         "Use dependencies from unknown/unverified sources",
         "Skip dependency updates for months",
         "Copy-paste code from untrusted sources"],
        "HIGH", ["ALL"]
    ),
    "bp_secure_cookies": _best_practice(
        "Secure Cookie Configuration", "WEB_SECURITY",
        "Set all security flags on cookies: HttpOnly, Secure, SameSite, proper expiry.",
        ["Set HttpOnly flag to prevent JavaScript access",
         "Set Secure flag for HTTPS-only transmission",
         "Set SameSite=Strict or Lax to prevent CSRF",
         "Set appropriate Max-Age/Expires"],
        ["Store sensitive data in localStorage (XSS vulnerable)",
         "Create cookies without HttpOnly flag for auth tokens",
         "Use SameSite=None without Secure flag"],
        "HIGH", ["Web", "React", "Next.js"]
    ),
    "bp_security_headers": _best_practice(
        "Security Headers", "WEB_SECURITY",
        "Set security headers on all HTTP responses to prevent common attacks.",
        ["Strict-Transport-Security: max-age=31536000; includeSubDomains",
         "Content-Security-Policy: default-src 'self'",
         "X-Content-Type-Options: nosniff",
         "X-Frame-Options: DENY",
         "Referrer-Policy: strict-origin-when-cross-origin",
         "Use helmet (Express) or Spring Security defaults"],
        ["Serve responses without security headers",
         "Allow framing from any origin",
         "Skip HSTS for HTTPS sites"],
        "HIGH", ["Web", "Express", "Spring Boot"]
    ),
    "bp_logging_security": _best_practice(
        "Secure Logging", "OPERATIONS",
        "Log security events but never sensitive data. Structure logs for analysis.",
        ["Log: authentication events, authorization failures, input validation errors",
         "Include: timestamp, user ID, action, IP, result (success/fail)",
         "Use structured logging (JSON) for machine parsing",
         "Set appropriate log levels: ERROR for failures, WARN for suspicious, INFO for audit"],
        ["Log passwords, tokens, API keys, or secrets",
         "Log PII (SSN, credit card numbers) in plaintext",
         "Use println/console.log for production logging",
         "Disable logging in production"],
        "HIGH", ["ALL"]
    ),
    "bp_csrf_protection": _best_practice(
        "CSRF Protection", "WEB_SECURITY",
        "Protect state-changing operations from Cross-Site Request Forgery.",
        ["Use CSRF tokens for traditional form submissions",
         "SameSite=Strict/Lax cookies prevent most CSRF",
         "Verify Origin/Referer headers on the server",
         "For SPAs with JWT in Authorization header: CSRF tokens not needed"],
        ["Disable CSRF protection without understanding the implications",
         "Use GET requests for state-changing operations",
         "Store auth tokens in regular cookies without SameSite"],
        "HIGH", ["Web", "Spring Boot", "Django", "Express"]
    ),
    "bp_rate_limiting": _best_practice(
        "Rate Limiting", "API_SECURITY",
        "Prevent abuse and DoS by limiting request rates at multiple levels.",
        ["Global: 1000 req/min per IP",
         "Auth endpoints: 5 req/min per IP (login, register, reset password)",
         "API endpoints: 100 req/min per authenticated user",
         "Use Redis-backed rate limiter for distributed systems",
         "Return 429 Too Many Requests with Retry-After header"],
        ["Allow unlimited requests to any endpoint",
         "Rate limit only at the application level (add WAF/CDN too)",
         "Use in-memory rate limiting in distributed systems"],
        "HIGH", ["ALL"]
    ),
    "bp_file_upload": _best_practice(
        "Secure File Upload", "WEB_SECURITY",
        "Validate file uploads thoroughly to prevent malware and abuse.",
        ["Validate file type by content (magic bytes), not just extension",
         "Limit file size (e.g., 10MB max)",
         "Generate random filenames — never use user-supplied names",
         "Store outside web root or in object storage (S3, GCS)",
         "Scan for malware before processing"],
        ["Trust the Content-Type header from the client",
         "Store uploaded files in a publicly accessible directory with original names",
         "Execute or include uploaded files without validation"],
        "HIGH", ["ALL"]
    ),
    "bp_env_security": _best_practice(
        "Environment Security", "OPERATIONS",
        "Separate configuration by environment. Never allow production debugging from outside.",
        ["Use separate configs for dev/staging/production",
         "Disable debug endpoints in production",
         "Use environment variables or secret managers for credentials",
         "Restrict production access to authorized personnel only",
         "Enable audit logging for all production access"],
        ["Use the same credentials across environments",
         "Leave debug/swagger endpoints enabled in production",
         "Commit .env files or secrets to git",
         "Give developers direct production database access"],
        "CRITICAL", ["ALL"]
    ),
}
