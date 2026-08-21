import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum CircuitState { closed, open, halfOpen }

class CircuitBreaker {
  int _consecutiveFailures = 0;
  CircuitState _state = CircuitState.closed;
  DateTime? _cooldownUntil;
  final int failureThreshold;
  final Duration cooldownDuration;

  CircuitBreaker({
    this.failureThreshold = 3,
    this.cooldownDuration = const Duration(seconds: 60),
  });

  bool get isAvailable {
    if (_state == CircuitState.open) {
      if (_cooldownUntil != null && DateTime.now().isBefore(_cooldownUntil!)) {
        return false;
      }
      _state = CircuitState.halfOpen;
    }
    return true;
  }

  void recordSuccess() {
    _consecutiveFailures = 0;
    _state = CircuitState.closed;
  }

  void recordFailure() {
    _consecutiveFailures++;
    if (_consecutiveFailures >= failureThreshold) {
      _state = CircuitState.open;
      _cooldownUntil = DateTime.now().add(cooldownDuration);
    }
  }

  String get stateName => _state.name;
}

class ApiClient {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  static const _secureStorage = FlutterSecureStorage();
  final CircuitBreaker _circuitBreaker = CircuitBreaker();
  static const _maxRetries = 3;

  Future<Map<String, String>> _authHeaders({bool withJson = false}) async {
    final token = await _secureStorage.read(key: 'auth_token');
    return {
      if (withJson) 'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  // 1-Click Quick Actions (Rollback, Backup, Clear Cache)
  Future<bool> triggerQuickAction(String actionType) async {
    try {
      final headers = await _authHeaders();
      final response = await http.post(
        Uri.parse('$baseUrl/api/admin/actions/$actionType'),
        headers: headers,
      );
      if (response.statusCode == 401 || response.statusCode == 403) {
        debugPrint('Action Trigger Error: not authorized (${response.statusCode}) — অ্যাডমিন লগইন প্রয়োজন');
      }
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('Action Trigger Error: $e');
      return false;
    }
  }

  // God Mode: Constitutional Rules
  Future<bool> updateGodRule(String key, bool value) async {
    try {
      final headers = await _authHeaders(withJson: true);
      final response = await http.post(
        Uri.parse('$baseUrl/api/admin/rules'),
        headers: headers,
        body: json.encode({'key': key, 'value': value ? 'true' : 'false'}),
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('God Mode Error: $e');
      return false;
    }
  }

  // বাংলা মন্তব্য: Swarm Emergency Stop — 'Hold to Kill' বাটনের আসল ব্যাকএন্ড কল।
  // আগে এই মেথডটি existই করত না, বাটনটি শুধু UI-তে অ্যানিমেশন দেখাত।
  Future<bool> haltSwarm() async {
    try {
      final headers = await _authHeaders();
      final response = await http.post(
        Uri.parse('$baseUrl/api/v1/swarm/halt'),
        headers: headers,
      );
      if (response.statusCode == 401 || response.statusCode == 403) {
        debugPrint('Halt Swarm Error: not authorized (${response.statusCode})');
      }
      return response.statusCode == 202;
    } catch (e) {
      debugPrint('Halt Swarm Error: $e');
      return false;
    }
  }

  Future<bool> resumeSwarm() async {
    try {
      final headers = await _authHeaders();
      final response = await http.post(
        Uri.parse('$baseUrl/api/v1/swarm/resume'),
        headers: headers,
      );
      return response.statusCode == 202;
    } catch (e) {
      debugPrint('Resume Swarm Error: $e');
      return false;
    }
  }
}
