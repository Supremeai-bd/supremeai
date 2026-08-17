import 'package:flutter/material.dart';
import 'tokens.dart';
import 'supreme_theme.dart';

class AppTheme {
  static ThemeData light = ThemeData(
    colorScheme: ColorScheme.fromSeed(
      seedColor: DesignTokens.colorBrandPrimaryLight,
      brightness: Brightness.light,
      primary: DesignTokens.colorBrandPrimaryLight,
      secondary: DesignTokens.colorBrandSecondaryLight,
    ),
    useMaterial3: true,
    scaffoldBackgroundColor: DesignTokens.colorBgVoidLight,
    textTheme: const TextTheme(
      displayLarge: TextStyle(color: DesignTokens.colorTextPrimaryLight, fontSize: DesignTokens.fontSize3xl, fontWeight: DesignTokens.fontWeightBold),
      headlineMedium: TextStyle(color: DesignTokens.colorTextPrimaryLight, fontSize: DesignTokens.fontSizeXl, fontWeight: DesignTokens.fontWeightSemibold),
      bodyLarge: TextStyle(color: DesignTokens.colorTextPrimaryLight, fontSize: DesignTokens.fontSizeBase, fontWeight: DesignTokens.fontWeightRegular),
      bodyMedium: TextStyle(color: DesignTokens.colorTextSecondaryLight, fontSize: DesignTokens.fontSizeSm, fontWeight: DesignTokens.fontWeightRegular),
      labelSmall: TextStyle(color: DesignTokens.colorTextDisabledLight, fontSize: DesignTokens.fontSizeXs, fontWeight: DesignTokens.fontWeightMedium),
    ),
  );

  static ThemeData dark = SupremeTheme.darkTheme;
}
