import 'package:flutter/material.dart';

// ============================================
// SupremeAI Flutter Design System
// Version: 2.0.0
// ============================================

class SupremeColors {
  // Background Colors
  static const Color bg = Color(0xFF0A0E1A);
  static const Color bgElevated = Color(0xFF111827);
  static const Color bgOverlay = Color(0xFF1A2236);
  static const Color bgModal = Color(0xFF0F172A);

  // Surface Colors
  static const Color surface = Color(0xFF111827);
  static const Color surfaceHover = Color(0xFF1A2236);
  static const Color surfaceActive = Color(0xFF1E293B);
  static const Color surfaceDisabled = Color(0xFF0F172A);

  // Border Colors
  static const Color border = Color(0xFF1F2937);
  static const Color borderHover = Color(0xFF374151);
  static const Color borderFocus = Color(0xFF6366F1);
  static const Color borderError = Color(0xFFEF4444);

  // Text Colors
  static const Color textPrimary = Color(0xFFF9FAFB);
  static const Color textSecondary = Color(0xFFE5E7EB);
  static const Color textMuted = Color(0xFF9CA3AF);
  static const Color textDisabled = Color(0xFF6B7280);

  // Accent Colors
  static const Color primary = Color(0xFF6366F1);
  static const Color primaryLight = Color(0xFF818CF8);
  static const Color primaryDark = Color(0xFF4F46E5);
  static const Color secondary = Color(0xFFA855F7);
  static const Color tertiary = Color(0xFFEC4899);

  // Semantic Colors
  static const Color success = Color(0xFF22C55E);
  static const Color successLight = Color(0xFF86EFAC);
  static const Color warning = Color(0xFFF59E0B);
  static const Color warningLight = Color(0xFFFCD34D);
  static const Color danger = Color(0xFFEF4444);
  static const Color dangerLight = Color(0xFFFCA5A5);
  static const Color info = Color(0xFF06B6D4);
  static const Color infoLight = Color(0xFF67E8F9);

  // Gradients
  static const Gradient gradientPrimary = LinearGradient(
    colors: [primary, secondary, tertiary],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const Gradient gradientSuccess = LinearGradient(
    colors: [success, Color(0xFF10B981)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const Gradient gradientInfo = LinearGradient(
    colors: [info, Color(0xFF3B82F6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const Gradient gradientWarning = LinearGradient(
    colors: [warning, danger],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

class SupremeSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double xxxl = 32;
  static const double xxxxl = 40;
  static const double xxxxxl = 48;
  static const double huge = 64;
}

class SupremeBorderRadius {
  static const double none = 0;
  static const double sm = 6;
  static const double md = 10;
  static const double lg = 14;
  static const double xl = 18;
  static const double xxl = 24;
  static const double full = 9999;
}

class SupremeShadows {
  static List<BoxShadow> get sm => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.3),
      blurRadius: 2,
      offset: const Offset(0, 1),
    ),
  ];

  static List<BoxShadow> get md => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.4),
      blurRadius: 12,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> get lg => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.5),
      blurRadius: 32,
      offset: const Offset(0, 8),
    ),
  ];

  static List<BoxShadow> glow(Color color) => [
    BoxShadow(
      color: color.withValues(alpha: 0.15),
      blurRadius: 20,
      spreadRadius: 0,
    ),
  ];

  static List<BoxShadow> get glowPrimary => glow(SupremeColors.primary);
  static List<BoxShadow> get glowSuccess => glow(SupremeColors.success);
  static List<BoxShadow> get glowDanger => glow(SupremeColors.danger);
}

class SupremeTypography {
  static const TextStyle heading1 = TextStyle(
    fontSize: 48,
    fontWeight: FontWeight.bold,
    color: SupremeColors.textPrimary,
    height: 1.2,
  );

  static const TextStyle heading2 = TextStyle(
    fontSize: 36,
    fontWeight: FontWeight.bold,
    color: SupremeColors.textPrimary,
    height: 1.25,
  );

  static const TextStyle heading3 = TextStyle(
    fontSize: 24,
    fontWeight: FontWeight.w600,
    color: SupremeColors.textPrimary,
    height: 1.3,
  );

  static const TextStyle heading4 = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    color: SupremeColors.textPrimary,
    height: 1.4,
  );

  static const TextStyle body = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.normal,
    color: SupremeColors.textSecondary,
    height: 1.6,
  );

  static const TextStyle bodySmall = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.normal,
    color: SupremeColors.textSecondary,
    height: 1.5,
  );

  static const TextStyle caption = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.normal,
    color: SupremeColors.textMuted,
    height: 1.4,
  );

  static const TextStyle label = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: SupremeColors.textPrimary,
    height: 1.4,
  );
}

class SupremeTheme {
  static ThemeData get darkTheme {
    return ThemeData.dark().copyWith(
      scaffoldBackgroundColor: SupremeColors.bg,
      primaryColor: SupremeColors.primary,
      colorScheme: const ColorScheme.dark(
        primary: SupremeColors.primary,
        secondary: SupremeColors.secondary,
        surface: SupremeColors.surface,
        error: SupremeColors.danger,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: SupremeColors.textPrimary,
        onError: Colors.white,
      ),
      cardTheme: CardTheme(
        color: SupremeColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SupremeBorderRadius.lg),
          side: const BorderSide(color: SupremeColors.border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: SupremeColors.bg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
          borderSide: const BorderSide(color: SupremeColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
          borderSide: const BorderSide(color: SupremeColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
          borderSide: const BorderSide(color: SupremeColors.borderFocus, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
          borderSide: const BorderSide(color: SupremeColors.borderError),
        ),
        contentPadding: const EdgeInsets.all(SupremeSpacing.lg),
        hintStyle: SupremeTypography.bodySmall.copyWith(color: SupremeColors.textMuted),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: SupremeColors.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(
            horizontal: SupremeSpacing.xl,
            vertical: SupremeSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
          ),
          textStyle: SupremeTypography.label,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: SupremeColors.primary,
          textStyle: SupremeTypography.label,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: SupremeColors.textSecondary,
          side: const BorderSide(color: SupremeColors.border),
          padding: const EdgeInsets.symmetric(
            horizontal: SupremeSpacing.xl,
            vertical: SupremeSpacing.md,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
          ),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: SupremeColors.surface,
        selectedItemColor: SupremeColors.primary,
        unselectedItemColor: SupremeColors.textMuted,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: SupremeColors.surface,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: SupremeTypography.heading4,
        iconTheme: IconThemeData(color: SupremeColors.textSecondary),
      ),
      dividerTheme: const DividerThemeData(
        color: SupremeColors.border,
        thickness: 1,
      ),
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.all(SupremeColors.borderHover),
        trackColor: WidgetStateProperty.all(Colors.transparent),
        thickness: WidgetStateProperty.all(8),
        radius: const Radius.circular(SupremeBorderRadius.full),
      ),
    );
  }
}
