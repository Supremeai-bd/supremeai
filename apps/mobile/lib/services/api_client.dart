import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  // বাংলা মন্তব্য: আগে এখানে হার্ডকোড করা 'https://api.supremeai.dev' ছিল, যা
  // api_service.dart-এর env-var-driven baseUrl-এর সাথে মিলত না (duplication/drift
  // risk)। এখন একই --dart-define=API_BASE_URL কনভেনশন অনুসরণ করা হচ্ছে।
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  static const _secureStorage = FlutterSecureStorage();

  // বাংলা মন্তব্য: আগে এই ক্লাসের কোনো মেথডেই Authorization header পাঠানো হতো না,
  // অথচ ব্যাকএন্ডের /api/admin/* রুটগুলো admin-role auth বাধ্যতামূলক করে —
  // ফলে প্রতিটি কল প্রোডাকশনে সবসময় 401/403 দিয়ে silently fail করত।
  // এখন token secure storage থেকে পড়া হয় — SharedPreferences নয়।
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
