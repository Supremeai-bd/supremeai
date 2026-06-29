import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiClient {
  static const String baseUrl = 'https://api.supremeai.dev'; // আপনার প্রোডাকশন URL দিন

  // 1-Click Quick Actions (Rollback, Backup, Clear Cache)
  Future<bool> triggerQuickAction(String actionType) async {
    try {
      final response = await http.post(Uri.parse('$baseUrl/api/admin/actions/$actionType'));
      return response.statusCode == 200;
    } catch (e) {
      print('Action Trigger Error: $e');
      return false;
    }
  }

  // God Mode: Constitutional Rules
  Future<bool> updateGodRule(String key, bool value) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/admin/rules'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'key': key, 'value': value ? 'true' : 'false'}),
      );
      return response.statusCode == 200;
    } catch (e) {
      print('God Mode Error: $e');
      return false;
    }
  }
}
