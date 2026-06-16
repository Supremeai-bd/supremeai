import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supremeai/providers/auth_provider.dart';
import 'package:supremeai/providers/orchestration_provider.dart';
import 'package:supremeai/providers/settings_provider.dart';
import 'package:supremeai/screens/dashboard/home_screen.dart';
import 'package:supremeai/services/localization_service.dart';
import 'package:http/http.dart' as http;
import 'package:supremeai/services/api_service.dart';

class FakeApiService implements ApiService {
  @override
  http.Client get client => throw UnimplementedError();

  @override
  Future<Map<String, dynamic>> getUserProfile() async => {'success': false};

  @override
  Future<Map<String, dynamic>> register(String email, String password, String displayName) async => {'success': false};

  @override
  Future<Map<String, dynamic>> firebaseLogin(String idToken) async => {'success': false};

  @override
  Future<void> logout() async {}

  @override
  Future<List<Map<String, dynamic>>> getConfiguredProviders() async => [];

  @override
  Future<String?> getToken() async => null;
}

class MockAuthProvider extends ChangeNotifier implements AuthProvider {
  @override
  AuthStatus get status => AuthStatus.guest;

  @override
  Map<String, dynamic>? get user => null;

  @override
  String? get token => null;

  @override
  String? get errorMessage => null;

  @override
  bool get isGuest => true;

  @override
  bool get isLoading => false;

  @override
  bool get isAdmin => false;

  @override
  Future<bool> login(String email, String password) async => false;

  @override
  Future<bool> loginWithGoogle() async => false;

  @override
  Future<void> continueAsGuest() async {}

  @override
  Future<void> logout() async {}

  @override
  void clearError() {}
}

class MockOrchestrationProvider extends ChangeNotifier implements OrchestrationProvider {
  bool _isLoading = false;
  OrchestrationError? _errorMessage;

  @override
  bool get isLoading => _isLoading;

  @override
  OrchestrationError? get error => _errorMessage;

  @override
  Map<String, dynamic>? get lastResult => null;

  @override
  bool get isOnline => true;

  @override
  List<Map<String, dynamic>> get offlineQueue => [];

  void setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }

  void setError(String message) {
    _errorMessage = OrchestrationError(message: message, type: OrchestrationErrorType.unknown);
    notifyListeners();
  }

  @override
  Future<void> orchestrateRequirement(String requirement, String token, {String? geminiKey, String? activeModel}) async {
    _isLoading = true;
    notifyListeners();
    await Future<void>.delayed(const Duration(milliseconds: 10));
    _isLoading = false;
    notifyListeners();
  }

  @override
  Future<void> generateProject(String token) async {}

  @override
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}

class MockSettingsProvider extends ChangeNotifier implements SettingsProvider {
  @override
  SupremeAISettings get settings => const SupremeAISettings();

  @override
  bool get isLoading => false;

  @override
  String? get error => null;

  @override
  void update(SupremeAISettings next) {}

  @override
  void setFullAuthority(bool enabled) {}

  @override
  Future<void> loadFromBackend({String? authToken}) async {}

  @override
  Future<bool> saveToBackend({String? authToken}) async => true;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    LocalizationService.setMockData({
      'app': {'title': 'SupremeAI'},
      'chat': {'describe': 'Describe what you want to build...'},
      'nav': {'chat': 'Chat', 'skills': 'Skills'},
    });
  });

  Widget createHomeScreen({AuthProvider? authProvider, OrchestrationProvider? orchestration}) {
    final auth = authProvider ?? MockAuthProvider();
    final orch = orchestration ?? MockOrchestrationProvider();

    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: auth),
        ChangeNotifierProvider<OrchestrationProvider>.value(value: orch),
        ChangeNotifierProvider<SettingsProvider>.value(value: MockSettingsProvider()),
      ],
      child: const MaterialApp(home: HomeScreen()),
    );
  }

  testWidgets('HomeScreen renders title and chat input', (WidgetTester tester) async {
    await tester.pumpWidget(createHomeScreen());
    await tester.pumpAndSettle();

    expect(find.text('SupremeAI'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
  });

  testWidgets('HomeScreen shows empty state prompt when no messages', (WidgetTester tester) async {
    await tester.pumpWidget(createHomeScreen());
    await tester.pumpAndSettle();

    expect(find.text('Describe what you want to build...'), findsOneWidget);
  });

  testWidgets('HomeScreen bottom navigation bar renders 5 destinations', (WidgetTester tester) async {
    await tester.pumpWidget(createHomeScreen());
    await tester.pumpAndSettle();

    expect(find.byType(NavigationDestination), findsNWidgets(5));
  });

  testWidgets('typing in chat input updates field value', (WidgetTester tester) async {
    await tester.pumpWidget(createHomeScreen());
    await tester.pumpAndSettle();

    final input = find.byType(TextField).first;
    await tester.enterText(input, 'Build a todo app');
    await tester.pump();

    expect(find.text('Build a todo app'), findsOneWidget);
  });

  testWidgets('shows loading indicator when orchestration is loading', (WidgetTester tester) async {
    final orch = MockOrchestrationProvider();
    orch.setLoading(true);

    await tester.pumpWidget(createHomeScreen(orchestration: orch));
    await tester.pumpAndSettle();

    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('displays error banner when orchestration has error', (WidgetTester tester) async {
    final orch = MockOrchestrationProvider();
    orch.setError('Network down');

    await tester.pumpWidget(createHomeScreen(orchestration: orch));
    await tester.pumpAndSettle();

    expect(find.text('Network down'), findsOneWidget);
  });

  testWidgets('logout button present in app bar when authenticated', (WidgetTester tester) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', 'token-abc');
    await prefs.setString('user_json', '{"username":"admin","role":"admin"}');

    await tester.pumpWidget(createHomeScreen(authProvider: MockAuthProvider()));
    await tester.pumpAndSettle(const Duration(seconds: 1));

    expect(find.byIcon(Icons.logout), findsOneWidget);
  });

  testWidgets('login icon shown when in guest mode', (WidgetTester tester) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('is_guest', true);

    await tester.pumpWidget(createHomeScreen(authProvider: MockAuthProvider()));
    await tester.pumpAndSettle(const Duration(seconds: 1));

    expect(find.byIcon(Icons.login), findsOneWidget);
  });
}
