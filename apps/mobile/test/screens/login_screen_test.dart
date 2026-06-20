import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:supremeai/providers/auth_provider.dart';
import 'package:supremeai/screens/login_screen.dart';

import 'package:supremeai/services/localization_service.dart';

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

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('LoginScreen renders title and login button', (WidgetTester tester) async {
    LocalizationService.setMockData({
      'app': {'title': 'SupremeAI'},
      'btn': {'login': 'Login'},
    });
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: MockAuthProvider(),
        child: const MaterialApp(home: LoginScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('SupremeAI'), findsOneWidget);
    expect(find.byType(ElevatedButton), findsOneWidget);
  });
}
