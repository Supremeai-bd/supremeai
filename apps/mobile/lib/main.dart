import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:provider/provider.dart';
import 'package:supremeai/providers/auth_provider.dart';
import 'package:supremeai/providers/settings_provider.dart';
import 'package:supremeai/providers/orchestration_provider.dart';
import 'package:supremeai/theme/app_theme.dart';
import 'package:supremeai/screens/login_screen.dart';
import 'package:supremeai/screens/dashboard/home_screen.dart';
import 'package:supremeai/services/localization_service.dart';
import 'package:supremeai/services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  await LocalizationService.load('bn');
  await NotificationService().initialize();
  runApp(const SupremeAIApp());
}

class SupremeAIApp extends StatelessWidget {
  const SupremeAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => SettingsProvider()),
        ChangeNotifierProvider(create: (_) => OrchestrationProvider()),
      ],
      child: Consumer<SettingsProvider>(
        builder: (context, settings, _) {
          return MaterialApp(
            title: 'SupremeAI',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.light,
            darkTheme: AppTheme.dark,
            themeMode: _getThemeMode(settings.settings.themeMode),
            home: const AuthWrapper(),
          );
        },
      ),
    );
  }

  ThemeMode _getThemeMode(String mode) {
    switch (mode) {
      case 'light': return ThemeMode.light;
      case 'dark': return ThemeMode.dark;
      default: return ThemeMode.system;
    }
  }
}

class AuthWrapper extends StatelessWidget {
  const AuthWrapper({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    
    if (auth.status == AuthStatus.authenticated || auth.status == AuthStatus.guest) {
      return const HomeScreen();
    }
    return const LoginScreen();
  }
}