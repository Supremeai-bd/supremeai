import 'package:flutter/foundation.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class SupremeAISettings {
  const SupremeAISettings({
    this.apiEndpoint = 'https://supremeai-a.web.app',
    this.apiKey = '',
    this.model = 'supremeai/1.5-pro',
    this.smallModel = 'supremeai/1.5-flash',
    this.version = 1,
    this.fullAuthority = false,
    this.permissions = const {
      'read': 'allow',
      'edit': 'ask',
      'bash': 'ask',
      'task': 'allow',
      'websearch': 'allow',
      'external_directory': 'deny',
    },
    this.shareMode = 'manual',
    this.enableExternalDirectory = false,
    this.themeMode = 'system',
  });

  final String apiEndpoint;
  final String apiKey;
  final String model;
  final String smallModel;
  final int version;
  final bool fullAuthority;
  final Map<String, String> permissions;
  final String shareMode;
  final bool enableExternalDirectory;
  final String themeMode;

  SupremeAISettings copyWith({
    String? apiEndpoint,
    String? apiKey,
    String? model,
    String? smallModel,
    int? version,
    bool? fullAuthority,
    Map<String, String>? permissions,
    String? shareMode,
    bool? enableExternalDirectory,
    String? themeMode,
  }) {
    return SupremeAISettings(
      apiEndpoint: apiEndpoint ?? this.apiEndpoint,
      apiKey: apiKey ?? this.apiKey,
      model: model ?? this.model,
      smallModel: smallModel ?? this.smallModel,
      version: version ?? this.version,
      fullAuthority: fullAuthority ?? this.fullAuthority,
      permissions: permissions ?? this.permissions,
      shareMode: shareMode ?? this.shareMode,
      enableExternalDirectory:
          enableExternalDirectory ?? this.enableExternalDirectory,
      themeMode: themeMode ?? this.themeMode,
    );
  }

  factory SupremeAISettings.fromJson(Map<String, dynamic> json) {
    final rawPermissions = (json['permissions'] as Map<String, dynamic>?) ?? {};
    return SupremeAISettings(
      apiEndpoint: json['apiEndpoint'] as String? ??
          'https://supremeai-a.web.app',
      apiKey: json['apiKey'] as String? ?? '',
      model: json['activeModel'] as String? ??
          json['model'] as String? ??
          'supremeai/1.5-pro',
      smallModel: json['smallModel'] as String? ?? 'supremeai/1.5-flash',
      version: (json['version'] as num?)?.toInt() ?? 1,
      fullAuthority: json['fullAuthority'] as bool? ?? false,
      permissions: rawPermissions.map(
        (key, value) => MapEntry(key, (value ?? 'ask').toString()),
      ),
      shareMode: json['shareMode'] as String? ?? 'manual',
      enableExternalDirectory:
          json['enableExternalDirectory'] as bool? ?? false,
      themeMode: json['themeMode'] as String? ?? 'system',
    );
  }

  Map<String, dynamic> toBackendJson() {
    return {
      'activeModel': model,
      'smallModel': smallModel,
      'version': version,
      'fullAuthority': fullAuthority,
      'permissions': permissions,
      'shareMode': shareMode,
      'enableExternalDirectory': enableExternalDirectory,
      'themeMode': themeMode,
    };
  }
}

class SettingsProvider extends ChangeNotifier {
  static const String _baseUrl = 'https://supremeai-a.web.app';

  SupremeAISettings _settings = const SupremeAISettings();
  bool _isLoading = false;
  String? _error;

  SupremeAISettings get settings => _settings;
  bool get isLoading => _isLoading;
  String? get error => _error;

  void update(SupremeAISettings next) {
    _settings = next;
    notifyListeners();
  }

  void setFullAuthority(bool enabled) {
    if (!enabled) {
      _settings = _settings.copyWith(fullAuthority: false);
      notifyListeners();
      return;
    }

    final elevatedPermissions = <String, String>{
      ..._settings.permissions,
      'read': 'allow',
      'edit': 'allow',
      'bash': 'allow',
      'task': 'allow',
      'websearch': 'allow',
      'external_directory':
          _settings.enableExternalDirectory ? 'allow' : 'deny',
    };

    _settings = _settings.copyWith(
      fullAuthority: true,
      permissions: elevatedPermissions,
    );
    notifyListeners();
  }

  Future<void> loadFromBackend({String? authToken}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/admin/config'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null && authToken.isNotEmpty)
            'Authorization': 'Bearer $authToken',
        },
      );

      if (response.statusCode >= 200 && response.statusCode < 300) {
        _settings = SupremeAISettings.fromJson(
          json.decode(response.body) as Map<String, dynamic>,
        );
      } else {
        _error = 'Failed to load settings (${response.statusCode})';
      }
    } catch (_) {
      _error = 'Unable to reach settings service';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> saveToBackend({String? authToken}) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await http.put(
        Uri.parse('$_baseUrl/api/admin/config'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null && authToken.isNotEmpty)
            'Authorization': 'Bearer $authToken',
        },
        body: json.encode(_settings.toBackendJson()),
      );

      if (response.statusCode >= 200 && response.statusCode < 300) {
        _settings = SupremeAISettings.fromJson(
          json.decode(response.body) as Map<String, dynamic>,
        );
        return true;
      }

      _error = 'Failed to save settings (${response.statusCode})';
      return false;
    } catch (_) {
      _error = 'Unable to save settings';
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
