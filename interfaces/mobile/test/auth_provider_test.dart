import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supremeai/providers/auth_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AuthProvider Tests', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('Initial status should be unauthenticated', () async {
      final authProvider = AuthProvider();
      // Wait for async _checkAuth to complete (reads prefs)
      await Future(() {}); // microtask
      await Future(() {}); // another cycle
      expect(authProvider.status, AuthStatus.unauthenticated);
    });

    test('continueAsGuest should update status to guest', () async {
      SharedPreferences.setMockInitialValues({});
      final authProvider = AuthProvider();
      await Future(() {}); // initial _checkAuth
      await Future(() {});

      await authProvider.continueAsGuest();
      await Future(() {}); // allow notification propagation

      expect(authProvider.status, AuthStatus.guest);
      expect(authProvider.isGuest, true);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('is_guest'), true);
    });

    test('logout should clear status and token', () async {
      // Setup: user is logged in as guest (no token, is_guest=true)
      SharedPreferences.setMockInitialValues({
        'is_guest': true,
      });

      final authProvider = AuthProvider();
      // Wait for _checkAuth to complete
      await Future(() {});
      await Future(() {});

      // Verify initial state is guest
      expect(authProvider.status, AuthStatus.guest);
      expect(authProvider.isGuest, true);

      // Perform logout
      await authProvider.logout();
      // Wait for async operations to propagate
      await Future(() {});

      // Verify logged out
      expect(authProvider.status, AuthStatus.unauthenticated);
      expect(authProvider.user, null);
      expect(authProvider.isGuest, false);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('is_guest'), null); // key removed after clear
    });

  });
}
