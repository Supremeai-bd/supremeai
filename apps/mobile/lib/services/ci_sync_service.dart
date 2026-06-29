import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/ci_job_model.dart';

class CiSyncService {
  static const String repo = 'paykaribazaronline/supremeai';
  static const String branch = 'main';
  static const String rawUrl = 'https://raw.githubusercontent.com/$repo/$branch';

  // লাইভ জব ফেচ করা
  Future<List<CiJobModel>> fetchLiveJobs() async {
    try {
      final response = await http.get(Uri.parse('$rawUrl/logs/ci/latest.json?t=${DateTime.now().millisecondsSinceEpoch}'));
      
      if (response.statusCode == 200) {
        final Map<String, dynamic> data = json.decode(response.body);
        final Map<String, dynamic> jobsMap = data['jobs'] ?? {};
        
        return jobsMap.entries.map((e) => CiJobModel.fromMap(e.key, e.value.toString())).toList();
      } else {
        throw Exception('Failed to load jobs');
      }
    } catch (e) {
      print('CI Sync Error: $e');
      return [];
    }
  }

  // টার্মিনালের জন্য মার্কডাউন লগ ফেচ করা
  Future<String> fetchLatestLog() async {
    try {
      final response = await http.get(Uri.parse('$rawUrl/logs/ci/latest.md?t=${DateTime.now().millisecondsSinceEpoch}'));
      if (response.statusCode == 200) {
        return response.body;
      }
      return 'Log not available.';
    } catch (e) {
      return 'Error fetching logs: $e';
    }
  }
}
