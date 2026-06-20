import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../services/localization_service.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Semantics(
        label: 'app.title'.tr(),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Semantics(
                header: true,
                child: Text(
                  'app.title'.tr(),
                  style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(height: 48),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Semantics(
                  button: true,
                  label: 'btn.login'.tr(),
                  child: ElevatedButton(
                    onPressed: () async {
                      final provider = context.read<AuthProvider>();
                      final success = await provider.login(
                        'demo@supremeai.com',
                        'Demo@123456',
                      );
                      if (context.mounted) {
                        if (success) {
                          // AuthProvider state change triggers UI update via Consumer
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(provider.errorMessage ?? 'error.server'.tr()),
                            ),
                          );
                        }
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                    ),
                    child: Text('btn.login'.tr()),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Semantics(
                label: 'Build Version: 1.0.1+fix',
                child: const Text(
                  'Build Version: 1.0.1+fix',
                  style: TextStyle(fontSize: 10, color: Colors.grey),
                  semanticsLabel: 'Build Version 1.0.1 fix',
                ),
              ),
              const SizedBox(height: 16),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Semantics(
                  button: true,
                  label: 'Google Sign-In',
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      final success = await context.read<AuthProvider>().loginWithGoogle();
                      if (context.mounted && !success) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(context.read<AuthProvider>().errorMessage ?? 'error.network'.tr()),
                          ),
                        );
                      }
                    },
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 50),
                    ),
                    icon: const Icon(Icons.login),
                    label: const Text('Google Sign-In'),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Semantics(
                button: true,
                label: 'Continue as guest',
                child: TextButton(
                  onPressed: () {
                    context.read<AuthProvider>().continueAsGuest();
                    // UI updates automatically via Consumer in main.dart
                  },
                  child: Text(
                    '${'nav.dashboard'.tr()} (Guest Mode)',
                    style: const TextStyle(color: Colors.blue),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Semantics(
                label: 'Guest mode has limited quota',
                child: Text(
                  '(${'onboarding.rate_limiting_desc'.tr()})',
                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                  semanticsLabel: 'Guest mode has limited quota',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
