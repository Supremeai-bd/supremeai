import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supremeai/providers/auth_provider.dart';
import 'package:supremeai/services/api_service.dart';
import 'package:http/http.dart' as http;

class FakeApiService implements ApiService {
  @override
  http.Client get client => throw UnimplementedError();

  bool registerSuccess = true;
  Map<String, dynamic> registerData = {};
  String? registerError;

  @override
  Future<Map<String, dynamic>> register(String email, String password, String displayName) async {
    if (registerSuccess) {
      return {'success': true, 'data': registerData};
    } else {
      return {'success': false, 'error': registerError ?? 'Error'};
    }
  }

  @override
  Future<Map<String, dynamic>> getUserProfile() async => {'success': false};

  @override
  Future<Map<String, dynamic>> firebaseLogin(String idToken) async => {'success': false};

  @override
  Future<void> logout() async {}

  @override
  Future<List<Map<String, dynamic>>> getConfiguredProviders() async => [];

  @override
  Future<String?> getToken() async => null;

  @override
  Future<Map<String, dynamic>> executeAgentTask(String task, {String? model}) async => {};

  @override
  Future<Map<String, dynamic>> getAgentStatus() async => {};
}

class MockAuthProvider extends ChangeNotifier implements AuthProvider {
  @override
  AuthStatus get status => AuthStatus.unauthenticated;

  @override
  Map<String, dynamic>? get user => null;

  @override
  String? get token => null;

  @override
  String? get errorMessage => null;

  @override
  bool get isGuest => false;

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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AuthProvider Edge Cases', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('login failure sets unauthenticated and error', () async {
      final auth = MockAuthProvider();
      await Future(() {});
      await Future(() {});

      final result = await auth.login('bad@test.com', 'wrong');
      expect(result, false);
      expect(auth.status, AuthStatus.unauthenticated);
    });

    test('loginWithGoogle returns false when sign-in cancelled', () async {
      final auth = MockAuthProvider();
      await Future(() {});
      await Future(() {});

      expect(auth.status, AuthStatus.unauthenticated);
    });

    test('logout clears auth state', () async {
      SharedPreferences.setMockInitialValues({'auth_token': 'tok', 'user_json': '{"username":"admin"}'});
      final auth = MockAuthProvider();
      await Future(() {});
      await Future(() {});

      await auth.logout();
      await Future(() {});
      expect(auth.token, null);
      expect(auth.user, null);
      expect(auth.status, AuthStatus.unauthenticated);
    });
  });
}
