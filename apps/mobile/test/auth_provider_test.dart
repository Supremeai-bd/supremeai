import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supremeai_mobile/providers/auth_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AuthProvider Tests', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
      FlutterSecureStorage.setMockInitialValues({});
    });

    test('Initial status should be unauthenticated', () async {
      final authProvider = AuthProvider();
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(authProvider.status, AuthStatus.unauthenticated);
    });

    test('continueAsGuest should update status to guest', () async {
      final authProvider = AuthProvider();
      await Future<void>.delayed(Duration.zero);

      await authProvider.continueAsGuest();
      await Future<void>.delayed(Duration.zero);

      expect(authProvider.status, AuthStatus.guest);
      expect(authProvider.isGuest, true);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('is_guest'), true);
    });

    test('logout should clear status and token', () async {
      final authProvider = AuthProvider();
      await Future<void>.delayed(Duration.zero);
      await authProvider.continueAsGuest();

      // Verify initial state is guest
      expect(authProvider.status, AuthStatus.guest);
      expect(authProvider.isGuest, true);

      // Perform logout
      await authProvider.logout();
      await Future<void>.delayed(Duration.zero);

      // Verify logged out
      expect(authProvider.status, AuthStatus.unauthenticated);
      expect(authProvider.user, null);
      expect(authProvider.isGuest, false);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('is_guest'), null); // key removed after clear
    });

  });
}
