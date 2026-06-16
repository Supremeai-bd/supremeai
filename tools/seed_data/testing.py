"""
Part 8: Testing Knowledge
Covers: Unit testing, integration testing, E2E, TDD, mocking, test patterns, coverage
~20 learnings + ~15 patterns + ~10 templates = 45 documents
"""
from seed_data.helpers import _learning, _pattern, _code_template

TESTING_LEARNINGS = {

    # ── Testing Fundamentals ───────────────────────────────────────────────
    "test_pyramid": _learning(
        "PATTERN", "TESTING",
        "Test pyramid: Many unit tests (fast, isolated), fewer integration tests (real dependencies), "
        "fewest E2E tests (slow, fragile). Ratio roughly 70/20/10. Unit tests run in seconds, "
        "integration in minutes, E2E in minutes. Run unit tests on every commit, integration on PR, E2E on deploy.",
        ["Unit: Test one class/function in isolation, mock dependencies, <10ms per test",
         "Integration: Test component interactions (controller+service+DB), use testcontainers",
         "E2E: Test full user flows (browser/API), Cypress/Playwright for web, Appium for mobile",
         "Contract: Pact tests for API contracts between services"],
        "HIGH", 0.97, times_applied=120,
        context={"applies_to": ["ALL"]}
    ),
    "test_tdd_cycle": _learning(
        "PATTERN", "TESTING",
        "TDD cycle: Red → Green → Refactor. (1) Write failing test first, (2) Write minimal code "
        "to pass, (3) Refactor with confidence. Benefits: Better design, fewer bugs, living documentation. "
        "Don't TDD everything — use for complex business logic and algorithmic code.",
        ["Red: @Test void shouldRejectNegativeAmount() { assertThrows(IllegalArgumentException.class, () -> new Money(-1, USD)); }",
         "Green: Money(BigDecimal amount, Currency c) { if(amount.compareTo(ZERO) < 0) throw new IllegalArgumentException(); }",
         "Refactor: Extract validation to Value Object, simplify constructor",
         "When to TDD: Complex logic, bug fixes (write test that reproduces bug first), domain models"],
        "HIGH", 0.94, times_applied=55,
        context={"applies_to": ["ALL"], "methodology": "Test-Driven Development"}
    ),
    "test_naming": _learning(
        "PATTERN", "TESTING",
        "Test naming: Describe behavior, not implementation. Format: should_[expectedBehavior]_when_[condition] "
        "or given_[context]_when_[action]_then_[outcome]. Group related tests with @Nested (JUnit) or describe (Jest).",
        ["Java: @Test void should_return_404_when_user_not_found()",
         "Jest: it('should return user profile when authenticated', async () => {...})",
         "Nested: @Nested class WhenUserIsAdmin { @Test void should_allow_delete() {...} }",
         "Python: def test_transfer_fails_when_insufficient_balance():"],
        "MEDIUM", 0.96, times_applied=80,
        context={"applies_to": ["JUnit", "Jest", "pytest", "ALL"]}
    ),

    # ── Unit Testing ───────────────────────────────────────────────────────
    "test_unit_java": _learning(
        "PATTERN", "TESTING",
        "Java unit testing: JUnit 5 + Mockito. @Mock for dependencies, @InjectMocks for class under test. "
        "Use verify() to check interactions. AssertJ for fluent assertions. "
        "@ParameterizedTest for data-driven tests. @Nested for test organization.",
        ["Setup: @ExtendWith(MockitoExtension.class) class UserServiceTest { @Mock UserRepository repo; @InjectMocks UserService service; }",
         "Mock: when(repo.findById(1L)).thenReturn(Optional.of(user));",
         "Assert: assertThat(result).isNotNull().extracting(User::getName).isEqualTo(\"John\");",
         "Parameterized: @ParameterizedTest @CsvSource({\"admin,true\", \"user,false\"}) void testRole(String role, boolean expected)"],
        "HIGH", 0.97, times_applied=110,
        context={"applies_to": ["Java", "Spring Boot"], "libs": ["JUnit 5", "Mockito", "AssertJ"]}
    ),
    "test_unit_react": _learning(
        "PATTERN", "TESTING",
        "React testing: React Testing Library + Jest/Vitest. Test behavior, not implementation. "
        "Query by role/label/text, not by class/id. Use userEvent for interactions. "
        "Mock API with MSW (Mock Service Worker). Don't test implementation details.",
        ["Render: render(<UserProfile userId='123' />);",
         "Query: screen.getByRole('heading', { name: /john/i }); screen.getByLabelText('Email');",
         "Interact: await userEvent.click(screen.getByRole('button', { name: 'Save' }));",
         "Assert: expect(screen.getByText('Profile updated')).toBeInTheDocument();"],
        "HIGH", 0.96, times_applied=85,
        context={"applies_to": ["React", "TypeScript"], "libs": ["Testing Library", "Jest", "MSW"]}
    ),
    "test_unit_python": _learning(
        "PATTERN", "TESTING",
        "Python testing: pytest + fixtures. Use fixtures for setup/teardown. "
        "Parametrize with @pytest.mark.parametrize. Mock with unittest.mock or pytest-mock. "
        "conftest.py for shared fixtures. Coverage with pytest-cov.",
        ["Fixture: @pytest.fixture def user_service(mock_repo): return UserService(mock_repo)",
         "Parametrize: @pytest.mark.parametrize('input,expected', [('admin',True), ('user',False)])",
         "Mock: mocker.patch('app.services.email.send', return_value=True)",
         "Run: pytest --cov=app --cov-report=html -v"],
        "HIGH", 0.96, times_applied=80,
        context={"applies_to": ["Python", "FastAPI", "Django"], "libs": ["pytest", "pytest-mock"]}
    ),
    "test_unit_flutter": _learning(
        "PATTERN", "TESTING",
        "Flutter testing: test package for unit, flutter_test for widgets. Use mocktail for mocking. "
        "Widget tests: pumpWidget, tap, expect. Use ProviderScope overrides for Riverpod testing. "
        "Golden tests for visual regression.",
        ["Unit: test('should calculate total', () { final cart = Cart(); cart.add(Item(price: 10)); expect(cart.total, equals(10)); });",
         "Widget: testWidgets('shows user name', (tester) async { await tester.pumpWidget(MaterialApp(home: UserCard(user: testUser))); expect(find.text('John'), findsOneWidget); });",
         "Mock: class MockUserRepo extends Mock implements UserRepository {}",
         "Riverpod: final container = ProviderContainer(overrides: [userRepoProvider.overrideWithValue(mockRepo)]);"],
        "HIGH", 0.95, times_applied=55,
        context={"applies_to": ["Flutter", "Dart"], "libs": ["mocktail", "flutter_test"]}
    ),

    # ── Integration Testing ────────────────────────────────────────────────
    "test_integration_spring": _learning(
        "PATTERN", "TESTING",
        "Spring Boot integration testing: @SpringBootTest for full context. @WebMvcTest for controllers. "
        "@DataJpaTest for repositories. Testcontainers for real databases. "
        "Use @ActiveProfiles('test') for test configuration.",
        ["Controller: @WebMvcTest(UserController.class) class UserControllerTest { @MockBean UserService service; @Autowired MockMvc mvc; @Test void list() { mvc.perform(get(\"/api/users\")).andExpect(status().isOk()); } }",
         "Repository: @DataJpaTest class UserRepoTest { @Autowired UserRepository repo; @Autowired TestEntityManager em; }",
         "Full: @SpringBootTest @Testcontainers class IntegrationTest { @Container static PostgreSQLContainer<?> pg = new PostgreSQLContainer<>(\"postgres:16\"); }",
         "Config: @ActiveProfiles(\"test\") + application-test.yml"],
        "HIGH", 0.96, times_applied=75,
        context={"applies_to": ["Spring Boot"], "libs": ["Testcontainers", "MockMvc"]}
    ),
    "test_integration_api": _learning(
        "PATTERN", "TESTING",
        "API integration testing: Test full HTTP request/response cycle. Use RestAssured (Java), "
        "httpx (Python), supertest (Node.js). Verify status codes, response body, headers. "
        "Test error cases: 400, 401, 403, 404, 422. Use test database with known seed data.",
        ["RestAssured: given().contentType(JSON).body(createDto).when().post(\"/api/users\").then().statusCode(201).body(\"name\", equalTo(\"John\"));",
         "httpx: response = await client.post('/api/users', json={'name': 'John'}); assert response.status_code == 201",
         "supertest: request(app).post('/api/users').send({name:'John'}).expect(201).expect(res => expect(res.body.name).toBe('John'))",
         "Error: given().when().get(\"/api/users/999\").then().statusCode(404).body(\"title\", equalTo(\"Not Found\"));"],
        "HIGH", 0.96, times_applied=70,
        context={"applies_to": ["ALL"], "libs": ["RestAssured", "httpx", "supertest"]}
    ),

    # ── E2E Testing ────────────────────────────────────────────────────────
    "test_e2e_playwright": _learning(
        "PATTERN", "TESTING",
        "Playwright E2E testing: Cross-browser testing (Chromium, Firefox, WebKit). "
        "Auto-waiting for elements. Network interception for API mocking. "
        "Visual comparison with screenshots. Trace viewer for debugging.",
        ["Navigate: await page.goto('/login');",
         "Interact: await page.getByLabel('Email').fill('user@test.com'); await page.getByRole('button', { name: 'Login' }).click();",
         "Assert: await expect(page.getByRole('heading')).toHaveText('Dashboard');",
         "API mock: await page.route('/api/users', route => route.fulfill({ json: mockUsers }));"],
        "HIGH", 0.95, times_applied=45,
        context={"applies_to": ["Web", "React", "Next.js"], "tool": "Playwright"}
    ),

    # ── Mocking ────────────────────────────────────────────────────────────
    "test_mocking_strategies": _learning(
        "PATTERN", "TESTING",
        "Mocking strategies: Mock at the boundary (HTTP, DB, filesystem). Don't mock what you don't own "
        "— wrap third-party libs in adapters, mock the adapter. Use stubs for queries, mocks for commands. "
        "Testcontainers > mocking for integration tests.",
        ["Boundary: Mock HTTP with WireMock/MSW, not internal service classes",
         "Adapter: interface EmailSender { void send(Email e); } mock EmailSender, not SmtpClient directly",
         "Stub: when(repo.findById(1L)).thenReturn(user); // for query testing",
         "Verify: verify(emailSender).send(argThat(e -> e.getTo().equals(\"user@x.com\"))); // for command testing"],
        "HIGH", 0.95, times_applied=65,
        context={"applies_to": ["ALL"]}
    ),
    "test_msw": _learning(
        "PATTERN", "TESTING",
        "Mock Service Worker (MSW): Intercept HTTP at the network level. "
        "Works in browser and Node.js. Define handlers: rest.get('/api/users', resolver). "
        "Use in tests AND development (mock backend during frontend dev).",
        ["Setup: const server = setupServer(rest.get('/api/users', (req, res, ctx) => res(ctx.json(mockUsers))))",
         "Test: beforeAll(() => server.listen()); afterEach(() => server.resetHandlers()); afterAll(() => server.close());",
         "Override: server.use(rest.get('/api/users', (req, res, ctx) => res(ctx.status(500))))",
         "Dev: Start MSW in service worker for browser-based API mocking during development"],
        "HIGH", 0.94, times_applied=40,
        context={"applies_to": ["React", "TypeScript", "Node.js"], "tool": "MSW"}
    ),

    # ── Coverage & Quality ─────────────────────────────────────────────────
    "test_coverage": _learning(
        "PATTERN", "TESTING",
        "Test coverage: 80% line coverage is a good target. 100% is usually wasteful. "
        "Focus on branch coverage — more meaningful than line coverage. "
        "Mutation testing (PIT for Java, Stryker for JS) for quality over quantity.",
        ["Java: ./gradlew test jacocoTestReport — generates HTML coverage report",
         "JS: jest --coverage --coverageThreshold='{\"global\":{\"branches\":80}}'",
         "Python: pytest --cov=app --cov-fail-under=80",
         "Mutation: PIT tests if your tests actually catch bugs, not just execute code"],
        "MEDIUM", 0.94, times_applied=50,
        context={"applies_to": ["ALL"], "target": "80% branch coverage"}
    ),
}

TESTING_PATTERNS = {
    "pat_test_service_java": _pattern(
        "JUnit 5 Service Test", "TESTING",
        "Complete unit test for a Spring service with mocks, assertions, and edge cases",
        "Testing service layer in Spring Boot",
        "@ExtendWith(MockitoExtension.class)\nclass UserServiceTest {\n    @Mock UserRepository repo;\n    @Mock PasswordEncoder encoder;\n    @InjectMocks UserService service;\n\n    @Test void create_shouldSaveUser() {\n        var dto = new CreateUserDTO(\"John\", \"j@x.com\", \"pass123\");\n        when(repo.existsByEmail(\"j@x.com\")).thenReturn(false);\n        when(encoder.encode(\"pass123\")).thenReturn(\"hashed\");\n        when(repo.save(any())).thenAnswer(inv -> { User u = inv.getArgument(0); u.setId(1L); return u; });\n\n        var result = service.create(dto);\n\n        assertThat(result.getId()).isEqualTo(1L);\n        assertThat(result.getEmail()).isEqualTo(\"j@x.com\");\n        verify(repo).save(argThat(u -> u.getPassword().equals(\"hashed\")));\n    }\n\n    @Test void create_shouldThrow_whenEmailExists() {\n        when(repo.existsByEmail(\"j@x.com\")).thenReturn(true);\n        assertThrows(DuplicateException.class, () -> service.create(new CreateUserDTO(\"John\",\"j@x.com\",\"pass\")));\n    }\n}",
        "JUnit 5 + Mockito", 0.97, times_used=100
    ),
    "pat_test_controller_spring": _pattern(
        "Spring WebMvcTest", "TESTING",
        "Controller test with MockMvc, JSON assertions, and error case testing",
        "Testing REST controllers in Spring Boot",
        "@WebMvcTest(UserController.class)\nclass UserControllerTest {\n    @Autowired MockMvc mvc;\n    @MockBean UserService service;\n\n    @Test void list_shouldReturn200() throws Exception {\n        when(service.findAll(any())).thenReturn(Page.empty());\n        mvc.perform(get(\"/api/v1/users\"))\n           .andExpect(status().isOk())\n           .andExpect(jsonPath(\"$.content\").isArray());\n    }\n\n    @Test void create_shouldReturn201() throws Exception {\n        var dto = new CreateUserDTO(\"John\", \"j@x.com\", \"password123\");\n        when(service.create(any())).thenReturn(new UserDTO(1L, \"John\", \"j@x.com\"));\n        mvc.perform(post(\"/api/v1/users\").contentType(APPLICATION_JSON).content(objectMapper.writeValueAsString(dto)))\n           .andExpect(status().isCreated())\n           .andExpect(jsonPath(\"$.name\").value(\"John\"));\n    }\n\n    @Test void create_shouldReturn400_whenInvalid() throws Exception {\n        mvc.perform(post(\"/api/v1/users\").contentType(APPLICATION_JSON).content(\"{}\"))\n           .andExpect(status().isBadRequest());\n    }\n}",
        "Spring Boot + MockMvc", 0.97, times_used=90
    ),
    "pat_test_react_component": _pattern(
        "React Component Test", "TESTING",
        "Component test with React Testing Library, user events, and async assertions",
        "Testing React components",
        "describe('UserProfile', () => {\n  it('should display user info', async () => {\n    server.use(rest.get('/api/users/1', (req, res, ctx) => res(ctx.json({ name: 'John', email: 'j@x.com' }))));\n    render(<UserProfile userId='1' />);\n    expect(await screen.findByText('John')).toBeInTheDocument();\n    expect(screen.getByText('j@x.com')).toBeInTheDocument();\n  });\n\n  it('should show error on fetch failure', async () => {\n    server.use(rest.get('/api/users/1', (req, res, ctx) => res(ctx.status(500))));\n    render(<UserProfile userId='1' />);\n    expect(await screen.findByText(/error/i)).toBeInTheDocument();\n  });\n\n  it('should update name on save', async () => {\n    render(<UserProfile userId='1' />);\n    await userEvent.clear(screen.getByLabelText('Name'));\n    await userEvent.type(screen.getByLabelText('Name'), 'Jane');\n    await userEvent.click(screen.getByRole('button', { name: 'Save' }));\n    expect(await screen.findByText('Saved!')).toBeInTheDocument();\n  });\n});",
        "React Testing Library + MSW", 0.96, times_used=75
    ),
    "pat_test_flutter_widget": _pattern(
        "Flutter Widget Test", "TESTING",
        "Widget test with pump, finder, and interaction testing",
        "Testing Flutter widgets",
        "void main() {\n  testWidgets('LoginScreen shows validation errors', (tester) async {\n    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));\n\n    // Tap login without entering credentials\n    await tester.tap(find.byType(ElevatedButton));\n    await tester.pumpAndSettle();\n\n    expect(find.text('Email is required'), findsOneWidget);\n    expect(find.text('Password is required'), findsOneWidget);\n\n    // Enter valid credentials\n    await tester.enterText(find.byKey(const Key('email')), 'test@example.com');\n    await tester.enterText(find.byKey(const Key('password')), 'password123');\n    await tester.tap(find.byType(ElevatedButton));\n    await tester.pumpAndSettle();\n\n    expect(find.text('Email is required'), findsNothing);\n  });\n}",
        "Flutter + flutter_test", 0.95, times_used=50
    ),
    "pat_test_api_integration": _pattern(
        "API Integration Test", "TESTING",
        "Full API integration test with database, authentication, and cleanup",
        "Testing REST APIs end-to-end",
        "@SpringBootTest(webEnvironment = RANDOM_PORT)\n@Testcontainers\nclass UserApiIntegrationTest {\n    @Container static PostgreSQLContainer<?> pg = new PostgreSQLContainer<>(\"postgres:16\");\n    @Autowired TestRestTemplate rest;\n    @Autowired UserRepository repo;\n\n    @BeforeEach void setup() { repo.deleteAll(); }\n\n    @Test void fullCrudFlow() {\n        // Create\n        var createResp = rest.postForEntity(\"/api/v1/users\", new CreateUserDTO(\"John\",\"j@x.com\",\"pass\"), UserDTO.class);\n        assertThat(createResp.getStatusCode()).isEqualTo(HttpStatus.CREATED);\n        Long id = createResp.getBody().getId();\n\n        // Read\n        var getResp = rest.getForEntity(\"/api/v1/users/\" + id, UserDTO.class);\n        assertThat(getResp.getBody().getName()).isEqualTo(\"John\");\n\n        // Update\n        rest.put(\"/api/v1/users/\" + id, new UpdateUserDTO(\"Jane\"));\n\n        // Delete\n        rest.delete(\"/api/v1/users/\" + id);\n        assertThat(rest.getForEntity(\"/api/v1/users/\" + id, String.class).getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);\n    }\n}",
        "Spring Boot + Testcontainers", 0.96, times_used=55
    ),
}

TESTING_TEMPLATES = {
    "tpl_jest_config": _code_template(
        "Jest Configuration", "TypeScript", "Jest",
        "configuration",
        "// jest.config.ts\nimport type { Config } from 'jest';\nconst config: Config = {\n  preset: 'ts-jest',\n  testEnvironment: 'jsdom',\n  setupFilesAfterSetup: ['<rootDir>/src/test/setup.ts'],\n  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },\n  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/**/*.d.ts', '!src/test/**'],\n  coverageThreshold: { global: { branches: 80, functions: 80, lines: 80 } },\n};\nexport default config;",
        "Jest configuration for TypeScript React project with coverage thresholds",
        ["jest", "typescript", "react", "configuration"]
    ),
    "tpl_pytest_conftest": _code_template(
        "pytest conftest.py", "Python", "pytest",
        "configuration",
        "import pytest\nfrom httpx import AsyncClient\nfrom app.main import app\nfrom app.db import get_db, init_test_db\n\n@pytest.fixture(scope='session')\ndef anyio_backend():\n    return 'asyncio'\n\n@pytest.fixture(scope='session', autouse=True)\nasync def setup_db():\n    await init_test_db()\n    yield\n\n@pytest.fixture\nasync def client():\n    async with AsyncClient(app=app, base_url='http://test') as ac:\n        yield ac\n\n@pytest.fixture\ndef auth_headers(test_user):\n    token = create_test_token(test_user.id)\n    return {'Authorization': f'Bearer {token}'}",
        "pytest configuration with async client, database setup, and auth fixtures",
        ["pytest", "python", "fastapi", "fixtures"]
    ),
    "tpl_spring_test_config": _code_template(
        "Spring Boot Test Config", "Java", "Spring Boot",
        "configuration",
        "// src/test/java/com/supremeai/config/TestConfig.java\n@TestConfiguration\npublic class TestConfig {\n    @Bean\n    public PasswordEncoder passwordEncoder() {\n        return new BCryptPasswordEncoder(4); // lower rounds for test speed\n    }\n}\n\n// src/test/resources/application-test.yml\n// spring:\n//   datasource:\n//     url: jdbc:tc:postgresql:16:///test\n//   jpa:\n//     hibernate.ddl-auto: create-drop\n//   logging.level.org.hibernate.SQL: DEBUG",
        "Spring Boot test configuration with faster password encoder and test DB",
        ["spring-boot", "test", "configuration", "testcontainers"]
    ),
    "tpl_msw_handlers": _code_template(
        "MSW API Handlers", "TypeScript", "MSW",
        "testing",
        "// src/test/mocks/handlers.ts\nimport { rest } from 'msw';\n\nconst mockUsers = [\n  { id: '1', name: 'John', email: 'john@test.com' },\n  { id: '2', name: 'Jane', email: 'jane@test.com' },\n];\n\nexport const handlers = [\n  rest.get('/api/users', (req, res, ctx) => {\n    return res(ctx.json(mockUsers));\n  }),\n  rest.get('/api/users/:id', (req, res, ctx) => {\n    const user = mockUsers.find(u => u.id === req.params.id);\n    return user ? res(ctx.json(user)) : res(ctx.status(404));\n  }),\n  rest.post('/api/users', async (req, res, ctx) => {\n    const body = await req.json();\n    return res(ctx.status(201), ctx.json({ id: '3', ...body }));\n  }),\n];",
        "MSW request handlers for mocking REST API in tests and development",
        ["msw", "mock", "api", "testing", "react"]
    ),
}
