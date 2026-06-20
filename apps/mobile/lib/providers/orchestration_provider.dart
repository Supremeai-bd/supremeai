import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:google_generative_ai/google_generative_ai.dart';


enum OrchestrationErrorType {
  network,
  serverError,
  unauthorized,
  timeout,
  unknown,
}

class OrchestrationError {
  final String message;
  final OrchestrationErrorType type;
  final bool recoverable;

  OrchestrationError({
    required this.message,
    required this.type,
    this.recoverable = true,
  });

  factory OrchestrationError.fromException(dynamic e) {
    if (e is TimeoutException) {
      return OrchestrationError(
        message:
            'The request timed out. Please check your connection and try again.',
        type: OrchestrationErrorType.timeout,
      );
    }
    if (e is http.ClientException) {
      return OrchestrationError(
        message:
            'Unable to connect to the server. Please check your internet connection.',
        type: OrchestrationErrorType.network,
      );
    }
    return OrchestrationError(
      message: 'An unexpected error occurred: ${e.toString()}',
      type: OrchestrationErrorType.unknown,
    );
  }

  factory OrchestrationError.fromStatusCode(int code) {
    switch (code) {
      case 401:
        return OrchestrationError(
          message: 'Your session has expired. Please log in again.',
          type: OrchestrationErrorType.unauthorized,
          recoverable: false,
        );
      case 403:
        return OrchestrationError(
          message: 'You do not have permission to perform this action.',
          type: OrchestrationErrorType.unauthorized,
          recoverable: false,
        );
      case 503:
        return OrchestrationError(
          message:
              'The service is temporarily unavailable. Please try again later.',
          type: OrchestrationErrorType.serverError,
        );
      default:
        return OrchestrationError(
          message: 'Server error (HTTP $code). Please try again.',
          type: OrchestrationErrorType.serverError,
        );
    }
  }
}

class OrchestrationProvider with ChangeNotifier {
  bool _isLoading = false;
  Map<String, dynamic>? _lastResult;
  OrchestrationError? _error;
  bool _isOnline = true;
  List<Map<String, dynamic>> _offlineQueue = [];

  bool get isLoading => _isLoading;
  Map<String, dynamic>? get lastResult => _lastResult;
  OrchestrationError? get error => _error;
  bool get isOnline => _isOnline;
  List<Map<String, dynamic>> get offlineQueue => _offlineQueue;

  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  static const String _scrapeChatUrl = String.fromEnvironment(
    'SCRAPE_CHAT_URL',
    defaultValue: '/api/chat/send',
  );

  String _buildFullUrl(String path) {
    final base = _baseUrl.endsWith('/') ? _baseUrl.substring(0, _baseUrl.length - 1) : _baseUrl;
    final cleanPath = path.startsWith('/') ? path : '/$path';
    if (cleanPath.startsWith('/api/chat/') || cleanPath.startsWith('/chat/')) {
      return '$base$_scrapeChatUrl';
    }
    return '$base$cleanPath';
  }

  static const String _cachedResultKey = 'orchestration_cached_result';
  static const String _offlineQueueKey = 'orchestration_offline_queue';

  OrchestrationProvider() {
    _initConnectivity();
    _loadCachedData();
  }

  Future<void> _initConnectivity() async {
    try {
      final result = await Connectivity().checkConnectivity();
      _updateConnectionStatus(result);

      Connectivity()
          .onConnectivityChanged
          .listen((List<ConnectivityResult> result) {
        _updateConnectionStatus(result);
      });
    } catch (_) {
      // Ignore connectivity check errors
    }
  }

  void _updateConnectionStatus(List<ConnectivityResult> result) {
    final wasOnline = _isOnline;
    _isOnline = result.isNotEmpty && result.first != ConnectivityResult.none;
    if (wasOnline != _isOnline) {
      notifyListeners();
    }
  }

  Future<void> _loadCachedData() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedResult = prefs.getString(_cachedResultKey);
      if (cachedResult != null) {
        _lastResult = json.decode(cachedResult);
      }
      final cachedQueue = prefs.getString(_offlineQueueKey);
      if (cachedQueue != null) {
        _offlineQueue =
            List<Map<String, dynamic>>.from(json.decode(cachedQueue));
      }
      notifyListeners();
    } catch (_) {
      // Ignore cache loading errors
    }
  }

  Future<void> _cacheResult(Map<String, dynamic> result) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_cachedResultKey, json.encode(result));
    } catch (_) {
      // Ignore caching errors
    }
  }

  Future<void> _queueOfflineOperation(Map<String, dynamic> operation) async {
    _offlineQueue.add(operation);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_offlineQueueKey, json.encode(_offlineQueue));
    } catch (_) {
      // Ignore queue saving errors
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }

  Future<void> orchestrateRequirement(String requirement, String token, {String? geminiKey, String? activeModel}) async {
    _isLoading = true;
    clearError();
    notifyListeners();

    final scrapeUrl = _buildFullUrl('/api/chat/send');

    if (_isOnline) {
      try {
        final headers = <String, String>{
          'Content-Type': 'application/json',
        };
        if (token.isNotEmpty == true) {
          headers['Authorization'] = 'Bearer $token';
        }
        headers['X-Use-Scrape'] = 'true';

        final response = await http
            .post(
              Uri.parse(scrapeUrl),
              headers: headers,
              body: json.encode({'message': requirement, 'userId': 'flutter-user'}),
            )
            .timeout(const Duration(seconds: 30));

        if (response.statusCode == 200) {
          final data = json.decode(response.body) as Map<String, dynamic>;
          _lastResult = {
            'status': 'COMPLETED',
            'mode': data['sourceType'] ?? 'AI',
            'answer': data['message'] ?? data['answer'] ?? '',
            'sources': data['sources'] ?? [],
            'confidence': data['confidence'] ?? 0.5,
            'chatType': data['chatType'] ?? 'UNKNOWN',
            'scrapedPages': data['scrapedPages'] ?? 0,
            'raw': data,
          };
          await _cacheResult(_lastResult!);
          _isLoading = false;
          notifyListeners();
          return;
        }
      } catch (e) {
        debugPrint('[SupremeAI] Scrape-backed chat failed, trying orchestrate: $e');
      }
    }

    if (_isOnline) {
      try {
        final response = await http
            .post(
              Uri.parse(_buildFullUrl('/api/orchestrate/requirement')),
              headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer $token',
              },
              body: json.encode({'requirement': requirement}),
            )
            .timeout(const Duration(seconds: 20));

        if (response.statusCode == 200) {
          _lastResult = json.decode(response.body);
          await _cacheResult(_lastResult!);
          _isLoading = false;
          notifyListeners();
          return;
        }
      } catch (e) {
        debugPrint('[SupremeAI] backend orchestrate failed: $e');
      }
    }

    if (geminiKey != null && geminiKey.isNotEmpty) {
      try {
        final model = GenerativeModel(model: activeModel ?? 'gemini-1.5-flash', apiKey: geminiKey);
        final content = [Content.text('As an AI Orchestrator for SupremeAI, analyze this requirement and provide a structured JSON response with "tasks", "priority", and "estimatedComplexity": $requirement')];
        final response = await model.generateContent(content);
        if (response.text != null) {
          final jsonStr = _extractJson(response.text!);
          _lastResult = {
            'status': 'COMPLETED',
            'mode': 'NativeGemini',
            'answer': response.text,
            ...json.decode(jsonStr),
          };
          await _cacheResult(_lastResult!);
          _isLoading = false;
          notifyListeners();
          return;
        }
      } catch (e) {
        _error = OrchestrationError(message: 'Native Gemini failed: $e', type: OrchestrationErrorType.unknown);
      }
    }

    if (!_isOnline) {
      await _queueOfflineOperation({
        'type': 'orchestrate',
        'requirement': requirement,
        'timestamp': DateTime.now().toIso8601String(),
      });
      _error = OrchestrationError(
        message: 'You are offline. Request queued for later sync.',
        type: OrchestrationErrorType.network,
      );
    } else {
      _error = OrchestrationError(
        message: 'All response sources failed. Please try again.',
        type: OrchestrationErrorType.serverError,
      );
    }

    _isLoading = false;
    notifyListeners();
  }

  String _extractJson(String text) {
    final start = text.indexOf('{');
    final end = text.lastIndexOf('}');
    if (start != -1 && end != -1) {
      return text.substring(start, end + 1);
    }
    return '{}';
  }

  Future<void> generateProject(String token) async {
    if (_lastResult == null) {
      _error = OrchestrationError(
        message: 'No orchestration result available to generate a project.',
        type: OrchestrationErrorType.unknown,
        recoverable: false,
      );
      notifyListeners();
      return;
    }

    _isLoading = true;
    clearError();
    notifyListeners();

    try {
      final response = await http
          .post(
            Uri.parse('$_baseUrl/api/orchestrate/generate'),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: json.encode(_lastResult),
          )
          .timeout(
            const Duration(seconds: 60),
            onTimeout: () => throw TimeoutException('Request timed out'),
          );

      if (response.statusCode == 200) {
        _lastResult = json.decode(response.body);
      } else {
        _error = OrchestrationError.fromStatusCode(response.statusCode);
      }
    } catch (e) {
      _error = OrchestrationError.fromException(e);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
