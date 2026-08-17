import 'package:flutter/material.dart';

// Represents the states from our Zod AuthStateEnum
enum AuthStatus {
  uninitialized,
  loggedOut,
  loggedIn,
}

class AuthStateShell extends StatelessWidget {
  final AuthStatus authStatus;
  final Widget splashScreen;
  final Widget loginScreen;
  final Widget dashboardScreen;

  const AuthStateShell({
    super.key,
    required this.authStatus,
    required this.splashScreen,
    required this.loginScreen,
    required this.dashboardScreen,
  });

  @override
  Widget build(BuildContext context) {
    // This is the core state machine routing logic
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 300),
      child: _getScreenForStatus(),
    );
  }

  Widget _getScreenForStatus() {
    switch (authStatus) {
      case AuthStatus.uninitialized:
        return KeyedSubtree(
          key: const ValueKey('splash'),
          child: splashScreen,
        );
      case AuthStatus.loggedOut:
        return KeyedSubtree(
          key: const ValueKey('login'),
          child: loginScreen,
        );
      case AuthStatus.loggedIn:
        return KeyedSubtree(
          key: const ValueKey('dashboard'),
          child: dashboardScreen,
        );
    }
  }
}
