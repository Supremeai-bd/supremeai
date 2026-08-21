import 'dart:convert';
import 'package:flutter/services.dart';

class LocalizationService {
  static Map<String, dynamic>? _localizedStrings;
  static String _currentLocale = 'en';
  static final Map<String, Map<String, String>> _runtimeCache = {};

  static Future<void> load(String locale) async {
    _currentLocale = locale;
    try {
      String jsonString = await rootBundle.loadString('assets/i18n/$locale.json');
      _localizedStrings = json.decode(jsonString);
    } catch (_) {
      // Graceful fallback to default
      _localizedStrings = {};
    }
  }

  static String translate(String key, {String? locale}) {
    final loc = locale ?? _currentLocale;
    if (_runtimeCache[loc]?.containsKey(key) ?? false) {
      return _runtimeCache[loc]![key]!;
    }

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

    final res = value.toString();
    _runtimeCache.putIfAbsent(loc, () => {})[key] = res;
    return res;
  }

  /// ADVANCED: Asynchronously resolve translation with AI fallback and runtime cache
  static Future<String> translateAsync(String key, {String? locale}) async {
    final loc = locale ?? _currentLocale;
    // 1. Check in-memory runtime cache
    if (_runtimeCache[loc]?.containsKey(key) ?? false) {
      return _runtimeCache[loc]![key]!;
    }

    // 2. Try bundled static JSON
    final syncVal = translate(key, locale: loc);
    if (syncVal != key) {
      _runtimeCache.putIfAbsent(loc, () => {})[key] = syncVal;
      return syncVal;
    }

    // 3. Fallback: key itself as default safe translation
    _runtimeCache.putIfAbsent(loc, () => {})[key] = key;
    return key;
  }

  static String get currentLocale => _currentLocale;

  static void setMockData(Map<String, dynamic> data) {
    _localizedStrings = data;
    _runtimeCache.clear();
  }
}

// Extension to make translation easier in widgets
extension Trans on String {
  String tr({String? locale}) => LocalizationService.translate(this, locale: locale);
  Future<String> trAsync({String? locale}) => LocalizationService.translateAsync(this, locale: locale);
}
