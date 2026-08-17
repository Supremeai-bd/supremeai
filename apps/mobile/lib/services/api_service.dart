import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiService {
  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  static const _secureStorage = FlutterSecureStorage();

  String? _token;
  final http.Client client;

  ApiService({http.Client? client}) : client = client ?? http.Client();

  Future<String?> getToken() async {
    if (_token != null) return _token;
    _token = await _secureStorage.read(key: 'auth_token');
    return _token;
  }

  Future<Map<String, dynamic>> firebaseLogin(String idToken) async {
    try {
      final response = await client
          .post(
            Uri.parse('$_baseUrl/api/auth/firebase-login'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'idToken': idToken}),
          )
          .timeout(const Duration(seconds: 30));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data['status'] == 'success') {
          _token = data['token'] ?? data['idToken'];
          if (_token != null) {
            await _secureStorage.write(key: 'auth_token', value: _token!);
          }
          return {'success': true, 'data': data};
        }
      }
      return {'success': false, 'error': 'Login failed (${response.statusCode})'};
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }

  Future<Map<String, dynamic>> register(
      String email, String password, String displayName) async {
    try {
      final response = await client
          .post(
            Uri.parse('$_baseUrl/api/auth/register'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'email': email,
              'password': password,
              'displayName': displayName,
            }),
          )
          .timeout(const Duration(seconds: 30));
      if (response.statusCode == 201) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return {'success': true, 'data': data};
      }
      return {'success': false, 'error': 'Registration failed (${response.statusCode})'};
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }

  Future<Map<String, dynamic>> getUserProfile() async {
    try {
      final token = await getToken();
      final response = await client
          .get(
            Uri.parse('$_baseUrl/api/auth/profile'),
            headers: {
              'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            },
          )
          .timeout(const Duration(seconds: 30));
      if (response.statusCode == 200) {
        return {'success': true, 'data': jsonDecode(response.body)};
      }
      return {'success': false, 'error': 'Failed to load profile'};
    } catch (e) {
      return {'success': false, 'error': '$e'};
    }
  }

  Future<List<Map<String, dynamic>>> getConfiguredProviders() async {
    try {
      final token = await getToken();
      final response = await client
          .get(
            Uri.parse('$_baseUrl/api/admin/providers/configured'),
            headers: {
              'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            },
          )
          .timeout(const Duration(seconds: 30));
      if (response.statusCode == 200) {
        final decoded = jsonDecode(response.body);
        final list = decoded['data']?['providers'] ?? decoded['data'] ?? decoded;
        if (list is List) {
          return List<Map<String, dynamic>>.from(list.map((e) => Map<String, dynamic>.from(e)));
        }
      }
    } catch (e) {
      // বাংলা মন্তব্য: এখানে empty list রিটার্ন করাই ইচ্ছাকৃত (ai_providers_screen.dart ফলব্যাক default providers দেখায়),
      // কিন্তু আগে এররটা সম্পূর্ণ silently মুছে যেত — এখন অন্তত debug log-এ দৃশ্যমান থাকবে
      debugPrint('getConfiguredProviders failed, falling back to defaults: $e');
    }
    return [];
  }

  Future<Map<String, dynamic>> getAgentStatus() async {
    try {
      final token = await getToken();
      final response = await client
          .get(
            Uri.parse('$_baseUrl/api/v1/agents/monitor/latency'),
            headers: {
              'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            },
          )
          .timeout(const Duration(seconds: 30));
      if (response.statusCode == 200) return {'success': true, 'data': jsonDecode(response.body)};
      return {'success': false, 'error': 'Failed to load agent status'};
    } catch (e) {
      return {'success': false, 'error': '$e'};
    }
  }

  Future<Map<String, dynamic>> executeAgentTask(
      String task, String taskType, {String? department}) async {
    try {
      final token = await getToken();
      final response = await client
          .post(
            Uri.parse('$_baseUrl/api/v1/agents/execute'),
            headers: {
              'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            },
            body: jsonEncode({
              'task': task,
              'task_type': taskType,
              'department': department,
            }),
          )
          .timeout(const Duration(seconds: 60));
      return {'success': response.statusCode == 200, 'data': jsonDecode(response.body)};
    } catch (e) {
      return {'success': false, 'error': '$e'};
    }
  }

  Future<void> logout() async {
    _token = null;
    await _secureStorage.delete(key: 'auth_token');
  }
}