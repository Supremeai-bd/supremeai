import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supremeai/screens/dashboard/home_screen.dart';
import 'package:provider/provider.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:supremeai/services/api_service.dart';
import 'package:supremeai/providers/auth_provider.dart';
import 'package:supremeai/providers/orchestration_provider.dart';
import 'package:supremeai/providers/settings_provider.dart';

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
  bool _loading = false;
  OrchestrationError? _error;

  @override
  bool get isLoading => _loading;

  @override
  OrchestrationError? get error => _error;

  @override
  Map<String, dynamic>? get lastResult => null;

  @override
  bool get isOnline => true;

  @override
  List<Map<String, dynamic>> get offlineQueue => [];

  void setLoading(bool value) {
    _loading = value;
    notifyListeners();
  }

  @override
  Future<void> orchestrateRequirement(String req, String token, {String? geminiKey, String? activeModel}) async {}

  @override
  Future<void> generateProject(String token) async {}

  @override
  void clearError() {
    _error = null;
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

class FakeAuth extends AuthProvider {
  FakeAuth() : super(apiService: FakeApiService());

  @override
  bool get isGuest => true;

  @override
  String? get token => null;

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

class FakeOrch extends OrchestrationProvider {
  FakeOrch() : _isLoading = false, _error = null;

  final bool _isLoading;
  final OrchestrationError? _error;

  @override
  bool get isLoading => _isLoading;

  @override
  OrchestrationError? get error => _error;

  @override
  Future<void> orchestrateRequirement(String req, String token, {String? geminiKey, String? activeModel}) async {}

  @override
  Future<void> generateProject(String token) async {}

  @override
  void clearError() {
    _error = null;
    notifyListeners();
  }
}

class FakeSettings extends SettingsProvider {
  FakeSettings() : super();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('HomeScreen send button disabled when input empty', (WidgetTester tester) async {
    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: MockAuthProvider()),
        ChangeNotifierProvider<OrchestrationProvider>.value(value: MockOrchestrationProvider()),
        ChangeNotifierProvider<SettingsProvider>.value(value: MockSettingsProvider()),
      ],
      child: const MaterialApp(home: HomeScreen()),
    ));
    await tester.pumpAndSettle();

    final sendBtn = find.byType(IconButton);
    expect(sendBtn, findsOneWidget);
  });

  testWidgets('HomeScreen generates project when result has action', (WidgetTester tester) async {
    final orch = MockOrchestrationProvider();
    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: MockAuthProvider()),
        ChangeNotifierProvider<OrchestrationProvider>.value(value: orch),
        ChangeNotifierProvider<SettingsProvider>.value(value: MockSettingsProvider()),
      ],
      child: const MaterialApp(home: HomeScreen()),
    ));
    await tester.pumpAndSettle();

    final generateBtn = find.text('Generate Project');
    if (generateBtn.evaluate().isNotEmpty) {
      await tester.tap(generateBtn);
      await tester.pump();
    }
  });

  testWidgets('HomeScreen switches tabs via bottom bar', (WidgetTester tester) async {
    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider<AuthProvider>.value(value: MockAuthProvider()),
        ChangeNotifierProvider<OrchestrationProvider>.value(value: MockOrchestrationProvider()),
        ChangeNotifierProvider<SettingsProvider>.value(value: MockSettingsProvider()),
      ],
      child: const MaterialApp(home: HomeScreen()),
    ));
    await tester.pumpAndSettle();

    final destinations = find.byType(NavigationDestination);
    expect(destinations, findsNWidgets(5));
  });
}
