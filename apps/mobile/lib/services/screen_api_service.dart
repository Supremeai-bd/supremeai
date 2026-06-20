import 'package:http/http.dart' as http;
import 'dart:convert';

class ScreenApiService {
  static const String _baseUrl = 'https://supremeai-a.web.app/api';

  Future<Map<String, dynamic>> ping(String screen) async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/screens/$screen'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {
      // fall through to local fallback
    }
    return _localFallback(screen);
  }

  Future<Map<String, dynamic>> action(String screen, Map<String, dynamic> payload) async {
    try {
      final response = await http
          .post(
            Uri.parse('$_baseUrl/screens/$screen/action'),
            headers: <String, String>{'Content-Type': 'application/json'},
            body: json.encode(payload),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {
      // fall through to local fallback
    }
    return _localFallback(screen);
  }

  Map<String, dynamic> _localFallback(String screen) {
    return {
      'status': 'ok',
      'mode': 'local',
      'screen': screen,
      'message': 'Backend unavailable — using local context.',
      'timestamp': DateTime.now().toIso8601String(),
      'data': <String, dynamic>{},
    };
  }
}
