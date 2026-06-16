"""
Engineering Practices: Accessibility, i18n, Documentation, Code Review, Agile,
Concurrency, Mobile, and Serverless patterns.
~25 learnings + ~6 best practices = ~31 documents
"""
from seed_data.helpers import _learning, _best_practice

PRACTICE_LEARNINGS = {

    # ── Accessibility ──────────────────────────────────────────────────────
    "practice_a11y_basics": _learning(
        "PATTERN", "ACCESSIBILITY",
        "Web accessibility (WCAG 2.1): Perceivable, Operable, Understandable, Robust. "
        "Use semantic HTML (nav, main, article, button). Add alt text to images. "
        "Ensure 4.5:1 color contrast ratio. Support keyboard navigation. Test with screen readers.",
        ["Semantic HTML: <button> not <div onclick>, <nav> not <div class='nav'>",
         "Alt text: <img alt='Dashboard showing user growth chart' />; alt='' for decorative images",
         "Contrast: Text 4.5:1 ratio (AA), large text 3:1. Use WebAIM contrast checker",
         "Focus: Visible focus indicators, logical tab order, skip-to-content link"],
        "HIGH", 0.96, times_applied=55,
        context={"applies_to": ["React", "HTML", "Web"]}
    ),
    "practice_a11y_aria": _learning(
        "PATTERN", "ACCESSIBILITY",
        "ARIA attributes: Use only when semantic HTML is insufficient. aria-label for custom buttons, "
        "aria-live for dynamic content, role for custom widgets. First rule: don't use ARIA if native "
        "HTML element exists. Test with NVDA, VoiceOver, or axe-core.",
        ["aria-label: <button aria-label='Close dialog'>X</button>",
         "aria-live: <div aria-live='polite'>3 new notifications</div> — announced by screen reader",
         "role: <div role='tablist'><button role='tab' aria-selected='true'>Tab 1</button></div>",
         "Testing: npm install @axe-core/react; axe-core browser extension; Lighthouse audit"],
        "MEDIUM", 0.95, times_applied=35,
        context={"applies_to": ["React", "HTML", "Web"]}
    ),

    # ── Internationalization ───────────────────────────────────────────────
    "practice_i18n": _learning(
        "PATTERN", "I18N",
        "Internationalization (i18n): Externalize all user-facing strings. Use ICU message format "
        "for plurals and interpolation. Format dates/numbers with Intl API. "
        "Support RTL layouts with logical CSS properties (margin-inline-start).",
        ["React: import { useTranslation } from 'react-i18next'; const { t } = useTranslation(); t('welcome', { name })",
         "Plurals: '{count, plural, =0 {No items} one {1 item} other {# items}}'",
         "Dates: new Intl.DateTimeFormat('de-DE', { dateStyle: 'long' }).format(date)",
         "RTL: Use margin-inline-start/end instead of margin-left/right"],
        "MEDIUM", 0.94, times_applied=30,
        context={"applies_to": ["React", "Flutter", "Web"]}
    ),
    "practice_i18n_flutter": _learning(
        "PATTERN", "I18N",
        "Flutter i18n: Use flutter_localizations + intl package. Define .arb files per locale. "
        "Generate with gen-l10n. Access via AppLocalizations.of(context).welcome. "
        "Support 50+ locales with minimal code changes.",
        ["Setup: flutter pub add flutter_localizations intl",
         "Define: lib/l10n/app_en.arb → { 'welcome': 'Welcome {name}', '@welcome': { 'placeholders': { 'name': {} } } }",
         "Generate: flutter gen-l10n → generates AppLocalizations class",
         "Use: Text(AppLocalizations.of(context)!.welcome('John'))"],
        "MEDIUM", 0.94, times_applied=25,
        context={"applies_to": ["Flutter", "Dart"]}
    ),

    # ── Documentation ──────────────────────────────────────────────────────
    "practice_api_docs": _learning(
        "PATTERN", "DOCUMENTATION",
        "API documentation: Use OpenAPI 3.0 (Swagger) spec. Auto-generate from annotations. "
        "Include request/response examples, error codes, authentication. "
        "Spring: springdoc-openapi. FastAPI: auto-generates /docs. Keep docs in sync with code.",
        ["Spring: @Operation(summary='Create user') @ApiResponse(responseCode='201')",
         "FastAPI: OpenAPI auto-generated at /docs (Swagger UI) and /redoc",
         "Best: Include curl examples, error response examples, rate limit info",
         "Versioning: OpenAPI spec per API version, publish to developer portal"],
        "HIGH", 0.95, times_applied=50,
        context={"applies_to": ["Spring Boot", "FastAPI", "ALL"]}
    ),
    "practice_adr": _learning(
        "PATTERN", "DOCUMENTATION",
        "Architecture Decision Records (ADR): Document key technical decisions. Format: "
        "Title, Status, Context, Decision, Consequences. Store in docs/adr/ in repo. "
        "Number sequentially (0001, 0002). Immutable once accepted — supersede with new ADR.",
        ["Template: # ADR-0001: Use PostgreSQL for primary database\n## Status: Accepted\n## Context: Need ACID transactions...\n## Decision: PostgreSQL 15\n## Consequences: Team needs SQL skills, managed hosting cost",
         "When: Language/framework choice, architecture change, security-critical decisions",
         "Tools: adr-tools CLI for scaffolding, or just markdown files",
         "Rule: Never delete/edit accepted ADRs — create new one that supersedes"],
        "MEDIUM", 0.94, times_applied=25,
        context={"applies_to": ["ALL"]}
    ),
    "practice_changelog": _learning(
        "PATTERN", "DOCUMENTATION",
        "Changelog management: Follow Keep a Changelog format. Sections: Added, Changed, Deprecated, "
        "Removed, Fixed, Security. Link each version to git diff. Automate with conventional commits. "
        "Tools: standard-version, release-please, semantic-release.",
        ["Format: ## [1.2.0] - 2026-04-06\n### Added\n- User export feature\n### Fixed\n- Login timeout issue",
         "Conventional commits: feat: add export → minor, fix: login timeout → patch, BREAKING: → major",
         "Automation: release-please GitHub Action auto-creates PRs with changelogs",
         "Link: [1.2.0]: https://github.com/org/repo/compare/v1.1.0...v1.2.0"],
        "MEDIUM", 0.94, times_applied=30,
        context={"applies_to": ["ALL"]}
    ),

    # ── Code Review ────────────────────────────────────────────────────────
    "practice_code_review": _learning(
        "PATTERN", "CODE_REVIEW",
        "Code review best practices: Review for correctness, security, performance, readability. "
        "Keep PRs small (<400 lines). Use checklists. Automate style checks (linters, formatters). "
        "Be constructive — suggest alternatives, explain why. Approve with minor nits.",
        ["Checklist: Correctness, edge cases, security (OWASP), tests added, naming, docs updated",
         "Size: <400 lines per PR. Break large changes into stacked PRs",
         "Automate: ESLint, Prettier, Checkstyle, Black — run in CI, don't review style manually",
         "Tone: 'Consider using X because Y' not 'This is wrong'. Ask questions, don't demand."],
        "HIGH", 0.95, times_applied=60,
        context={"applies_to": ["ALL"]}
    ),
    "practice_pr_template": _learning(
        "PATTERN", "CODE_REVIEW",
        "PR template: What (summary), Why (motivation/ticket), How (approach), Testing (what was tested), "
        "Screenshots (for UI changes). Link to issue/ticket. Include deployment notes if needed.",
        ["Template: ## What\nAdd user export feature\n## Why\nRequested in JIRA-123\n## How\nNew ExportService + CSV writer\n## Testing\nUnit tests + manual test with 10K users\n## Screenshots\n[attached]",
         "Auto-link: Mention issue number → GitHub auto-closes on merge",
         "Reviewers: Auto-assign via CODEOWNERS file",
         "Labels: Feature, bugfix, breaking-change, security for categorization"],
        "MEDIUM", 0.94, times_applied=40,
        context={"applies_to": ["ALL"]}
    ),

    # ── Agile & Process ────────────────────────────────────────────────────
    "practice_agile_scrum": _learning(
        "PATTERN", "AGILE",
        "Scrum essentials: Sprint (1-2 weeks), daily standup (15min), sprint review, retrospective. "
        "Product backlog → sprint backlog → done. Definition of done: coded, tested, reviewed, documented. "
        "Velocity = story points completed per sprint. Use for planning.",
        ["Sprint planning: Team commits to sprint backlog items based on velocity",
         "Daily standup: What I did, what I'll do, any blockers — 15 minutes max",
         "Retro: What went well, what didn't, action items for next sprint",
         "Estimation: Planning poker, T-shirt sizes (S/M/L/XL), story points (Fibonacci)"],
        "MEDIUM", 0.94, times_applied=50,
        context={"applies_to": ["ALL"]}
    ),
    "practice_kanban": _learning(
        "PATTERN", "AGILE",
        "Kanban: Continuous flow, no fixed sprints. Columns: Backlog → In Progress → Review → Done. "
        "WIP limits (e.g., max 3 items in progress). Pull-based — pick next item when capacity available. "
        "Measure: Cycle time (start → done), lead time (request → done), throughput.",
        ["WIP limit: Max 3 items in 'In Progress' column — forces finishing before starting",
         "Metrics: Cycle time target <3 days for features, <1 day for bugs",
         "When to use: Maintenance, support, ops work — no fixed iterations needed",
         "Tools: Jira, Linear, GitHub Projects — all support Kanban boards"],
        "MEDIUM", 0.93, times_applied=35,
        context={"applies_to": ["ALL"]}
    ),

    # ── Advanced Concurrency ───────────────────────────────────────────────
    "practice_reactive": _learning(
        "PATTERN", "CONCURRENCY",
        "Reactive programming: Non-blocking, backpressure-aware data streams. "
        "Project Reactor (Spring WebFlux), RxJS (Angular), RxDart (Flutter). "
        "Use for: High-throughput APIs, event streams, real-time data. Avoid for simple CRUD.",
        ["WebFlux: Mono<User> getUser(Long id) → non-blocking, supports 10K+ concurrent connections",
         "RxJS: this.http.get('/api/users').pipe(map(r => r.data), catchError(handleError))",
         "Backpressure: Prevent fast producer from overwhelming slow consumer",
         "When NOT to use: Simple CRUD with <100 concurrent users — overhead not worth it"],
        "MEDIUM", 0.94, times_applied=35,
        context={"applies_to": ["Java", "TypeScript", "Dart"]}
    ),
    "practice_virtual_threads": _learning(
        "PATTERN", "CONCURRENCY",
        "Java 21+ virtual threads: Lightweight threads (millions possible). Replace thread pools for IO-bound work. "
        "spring.threads.virtual.enabled=true in Spring Boot 3.2+. Don't use for CPU-bound work. "
        "Don't pin virtual threads with synchronized blocks — use ReentrantLock instead.",
        ["Enable: spring.threads.virtual.enabled=true — all request handling uses virtual threads",
         "Direct: Thread.startVirtualThread(() -> { /* IO-bound work */ });",
         "Structured: try (var scope = new StructuredTaskScope.ShutdownOnFailure()) { scope.fork(() -> callServiceA()); scope.fork(() -> callServiceB()); scope.join(); }",
         "Warning: Don't use synchronized — it pins the carrier thread. Use ReentrantLock."],
        "HIGH", 0.95, times_applied=30,
        context={"applies_to": ["Java"]}
    ),

    # ── Mobile Platform-specific ───────────────────────────────────────────
    "practice_mobile_native_ios": _learning(
        "PATTERN", "MOBILE",
        "iOS development: Swift + SwiftUI (declarative UI) or UIKit (imperative). "
        "Xcode for IDE, CocoaPods/SPM for dependencies. App Store review (1-3 days). "
        "Architecture: MVVM + Combine. Keychain for secure storage. Push via APNs.",
        ["SwiftUI: struct ContentView: View { var body: some View { Text('Hello') } }",
         "MVVM: @ObservableObject class ViewModel { @Published var items: [Item] = [] }",
         "Storage: Keychain for tokens, UserDefaults for preferences, CoreData for local DB",
         "Signing: Xcode → Signing & Capabilities → auto-manage or manual provisioning profile"],
        "MEDIUM", 0.93, times_applied=30,
        context={"applies_to": ["Swift", "iOS"]}
    ),
    "practice_mobile_native_android": _learning(
        "PATTERN", "MOBILE",
        "Android development: Kotlin + Jetpack Compose (declarative) or XML views. "
        "Android Studio IDE, Gradle build. Architecture: MVVM + ViewModel + LiveData/Flow. "
        "Room for local DB, DataStore for preferences, EncryptedSharedPreferences for secrets.",
        ["Compose: @Composable fun Greeting(name: String) { Text(text = \"Hello $name\") }",
         "ViewModel: class MainViewModel : ViewModel() { val items = MutableStateFlow<List<Item>>(emptyList()) }",
         "Room: @Entity data class User(@PrimaryKey val id: Int, val name: String)",
         "Navigation: NavController + NavGraph with Compose Navigation"],
        "MEDIUM", 0.93, times_applied=30,
        context={"applies_to": ["Kotlin", "Android"]}
    ),
    "practice_app_store_deploy": _learning(
        "PATTERN", "MOBILE",
        "App store deployment: iOS → TestFlight for beta, App Store Connect for release (review 1-3 days). "
        "Android → Internal/Closed/Open testing tracks in Google Play Console (review <1 day). "
        "Automate with Fastlane (build, sign, upload). Version bump strategy: semver.",
        ["Fastlane: fastlane ios release → build, sign, upload to TestFlight",
         "Android: fastlane android deploy → bundle, sign, upload to Play Store internal track",
         "CI: GitHub Actions + Fastlane for automated release on tag push",
         "Gotchas: iOS review rejections (metadata, privacy policy, crashes), Android policy (permissions)"],
        "MEDIUM", 0.93, times_applied=25,
        context={"applies_to": ["Flutter", "iOS", "Android"]}
    ),
}

PRACTICE_BEST_PRACTICES = {
    "bp_accessibility_checklist": _best_practice(
        "Accessibility Checklist", "ACCESSIBILITY",
        "Ensure all web applications meet WCAG 2.1 AA standards",
        ["Use semantic HTML elements (button, nav, main, article, aside)",
         "Add alt text to all informative images",
         "Ensure 4.5:1 color contrast ratio for normal text",
         "Support full keyboard navigation with visible focus indicators",
         "Use aria-live regions for dynamic content updates",
         "Test with screen reader (NVDA/VoiceOver) before release"],
        ["Don't use div/span as clickable elements without role and keyboard handler",
         "Don't rely solely on color to convey information",
         "Don't remove focus outlines without providing alternative",
         "Don't use placeholder text as the only label"],
        "HIGH", ["React", "HTML", "Web", "Flutter"]
    ),
    "bp_documentation_standards": _best_practice(
        "Documentation Standards", "DOCUMENTATION",
        "Maintain clear, up-to-date documentation for all projects",
        ["Write README with setup, run, test, deploy instructions",
         "Document API endpoints with OpenAPI/Swagger",
         "Create ADRs for significant technical decisions",
         "Maintain CHANGELOG.md with each release",
         "Include inline code comments for complex business logic only",
         "Write runbooks for production incident response"],
        ["Don't write comments that restate the code",
         "Don't let docs become stale — update docs with code changes",
         "Don't document internal implementation details in public API docs",
         "Don't skip error code documentation"],
        "MEDIUM", ["ALL"]
    ),
    "bp_code_review_etiquette": _best_practice(
        "Code Review Etiquette", "CODE_REVIEW",
        "Conduct productive, respectful code reviews that improve code quality",
        ["Keep PRs under 400 lines of code",
         "Provide constructive feedback with reasoning",
         "Approve with minor nits — don't block on style preferences",
         "Use automated linters for style enforcement",
         "Review for correctness, security, and edge cases first",
         "Respond to reviews within 24 hours"],
        ["Don't leave vague comments like 'This is wrong'",
         "Don't request changes for personal style preferences covered by linter",
         "Don't approve without actually reading the code",
         "Don't pile on — one reviewer flagging an issue is enough"],
        "HIGH", ["ALL"]
    ),
    "bp_i18n_guidelines": _best_practice(
        "Internationalization Guidelines", "I18N",
        "Build applications ready for multiple languages and locales",
        ["Externalize all user-facing strings from day one",
         "Use ICU message format for plurals and interpolation",
         "Format dates, numbers, currency with Intl API or locale-aware libraries",
         "Support RTL layouts with CSS logical properties",
         "Test with pseudo-localization to catch hardcoded strings",
         "Allow 30-50% text expansion for translations"],
        ["Don't concatenate translated strings — use templates with placeholders",
         "Don't hardcode date/number formats",
         "Don't assume all languages are LTR",
         "Don't use images containing text — use SVGs with translatable labels"],
        "MEDIUM", ["React", "Flutter", "Web"]
    ),
    "bp_mobile_development": _best_practice(
        "Mobile Development Best Practices", "MOBILE",
        "Build high-quality mobile applications across platforms",
        ["Handle offline scenarios gracefully with local caching",
         "Optimize for battery — minimize background work, batch network requests",
         "Request permissions at point of use, not on launch",
         "Test on real devices, not just emulators",
         "Support deep linking for navigation from external sources",
         "Implement crash reporting (Crashlytics, Sentry)"],
        ["Don't block the UI thread with heavy computation",
         "Don't ignore platform design guidelines (Material Design, HIG)",
         "Don't request unnecessary permissions",
         "Don't hardcode API URLs — use environment configs"],
        "HIGH", ["Flutter", "iOS", "Android"]
    ),
    "bp_serverless_practices": _best_practice(
        "Serverless Best Practices", "CLOUD",
        "Design efficient, cost-effective serverless applications",
        ["Keep functions small and single-purpose",
         "Use environment variables for configuration",
         "Implement structured logging with request correlation IDs",
         "Set memory/timeout limits appropriate to function workload",
         "Use provisioned concurrency for latency-critical functions",
         "Design for idempotency — functions may be invoked multiple times"],
        ["Don't use serverless for long-running tasks (>15 min)",
         "Don't store state in function memory — use external store",
         "Don't ignore cold start impact on user experience",
         "Don't create monolithic functions that do everything"],
        "MEDIUM", ["AWS Lambda", "Cloud Functions", "Azure Functions"]
    ),
}
