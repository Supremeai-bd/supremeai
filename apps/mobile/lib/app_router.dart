// apps/mobile/lib/app_router.dart
// Type-safe GoRouter navigation configuration for Flutter Mobile
// বাংলা মন্তব্য: গো-রাউটার দ্বারা চালিত টাইপ-সেইফ ন্যাভিগেশন সিস্টেম এবং ডিপ-লিংকিং সাপোর্ট।

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:supremeai/screens/login_screen.dart';
import 'package:supremeai/screens/dashboard/main_shell.dart';
import 'package:supremeai/screens/settings_screen.dart';
import 'package:supremeai/screens/byoc_hub_screen.dart';
import 'package:supremeai/screens/wallet_screen.dart';
import 'package:supremeai/screens/api_keys_screen.dart';
import 'package:supremeai/screens/onboarding/onboarding_screen.dart';
import 'package:supremeai/screens/notifications/notifications_screen.dart';
import 'package:supremeai/screens/quota/quota_screen.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const MainShell(),
    ),
    GoRoute(
      path: '/onboarding',
      builder: (context, state) => const OnboardingScreen(),
    ),
    GoRoute(
      path: '/notifications',
      builder: (context, state) => const NotificationsScreen(),
    ),
    GoRoute(
      path: '/quota',
      builder: (context, state) => const QuotaScreen(),
    ),
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/settings',
      builder: (context, state) => const SettingsScreen(),
    ),
    GoRoute(
      path: '/byoc',
      builder: (context, state) => const ByocHubScreen(),
    ),
    GoRoute(
      path: '/api-keys',
      builder: (context, state) => const ApiKeysScreen(),
    ),
    GoRoute(
      path: '/wallet',
      builder: (context, state) => const WalletScreen(),
    ),
  ],
  errorBuilder: (context, state) => Scaffold(
    backgroundColor: const Color(0xFF0F172A),
    body: Center(
      child: Text(
        '404 — Page Not Found\n${state.error}',
        textAlign: TextAlign.center,
        style: const TextStyle(color: Colors.redAccent, fontSize: 16),
      ),
    ),
  ),
);
