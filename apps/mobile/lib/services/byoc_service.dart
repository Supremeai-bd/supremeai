import 'dart:convert';
import 'api_service.dart';

class ByocService {
  final ApiService _apiService;
  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  ByocService({ApiService? apiService}) : _apiService = apiService ?? ApiService();

  /// Uploads and encrypts GCP Service Account JSON credentials.
  /// Zero-Trust: The raw content is passed directly, avoiding caching or local device storage.
  Future<Map<String, dynamic>> uploadCredentials(Map<String, dynamic> credentials) async {
    // বাংলা মন্তব্য: সরাসরি জিরো-ট্রাস্ট মেমরি ব্যবহারের মাধ্যমে ক্রেডেনশিয়াল আপলোড করা হচ্ছে
    try {
      final token = await _apiService.getToken();
      final response = await _apiService.client.post(
        Uri.parse('$_baseUrl/api/byoc/credentials'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'provider': 'gcp',
          'gcp_credentials': credentials,
        }),
      );

      final responseData = jsonDecode(response.body);
      if (response.statusCode == 200) {
        return {'success': true, 'message': responseData['message'] ?? 'Uploaded successfully.'};
      } else {
        return {'success': false, 'error': responseData['detail'] ?? 'Upload failed.'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }

  /// Triggers a container deployment task inside the user's BYOC environment.
  Future<Map<String, dynamic>> deployContainer(String skillName) async {
    try {
      final token = await _apiService.getToken();
      final response = await _apiService.client.post(
        Uri.parse('$_baseUrl/api/byoc/deploy'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'skill_name': skillName,
          'provider': 'gcp',
        }),
      );

      final responseData = jsonDecode(response.body);
      if (response.statusCode == 200) {
        return {'success': true, 'job_id': responseData['job_id'], 'message': responseData['message']};
      } else {
        return {'success': false, 'error': responseData['detail'] ?? 'Deployment failed.'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }

  /// Fetches the live deployment logs and execution state.
  Future<Map<String, dynamic>> getDeploymentStatus(String jobId) async {
    try {
      final token = await _apiService.getToken();
      final response = await _apiService.client.get(
        Uri.parse('$_baseUrl/api/byoc/status/$jobId'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        return {'success': true, 'job': jsonDecode(response.body)};
      } else {
        final responseData = jsonDecode(response.body);
        return {'success': false, 'error': responseData['detail'] ?? 'Failed to fetch status.'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }
}
