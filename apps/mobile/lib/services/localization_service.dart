import 'dart:convert';
import 'package:flutter/services.dart';

class LocalizationService {
  static Map<String, dynamic>? _localizedStrings;
  static String _currentLocale = 'en';

  static Future<void> load(String locale) async {
    _currentLocale = locale;
    String jsonString = await rootBundle.loadString('assets/i18n/$locale.json');
    _localizedStrings = json.decode(jsonString);
  }

  static String translate(String key) {
    if (_localizedStrings == null) return key;

    List<String> keys = key.split('.');
    dynamic value = _localizedStrings;

    for (var k in keys) {
      if (value is Map && value.containsKey(k)) {
        value = value[k];
      } else {
        return key;
      }
    }

    return value.toString();
  }

  static String get currentLocale => _currentLocale;

  static void setMockData(Map<String, dynamic> data) {
    _localizedStrings = data;
  }
}

// Extension to make translation easier in widgets
extension Trans on String {
  String tr() => LocalizationService.translate(this);
}
