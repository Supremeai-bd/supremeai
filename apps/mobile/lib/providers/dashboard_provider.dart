import 'package:flutter/foundation.dart';
import '../models/ci_job_model.dart';
import '../services/ci_sync_service.dart';
import '../services/api_client.dart';

class DashboardProvider with ChangeNotifier {
  final CiSyncService _syncService = CiSyncService();
  final ApiClient _apiClient = ApiClient();

  List<CiJobModel> _jobs = [];
  bool _isLoading = false;
  bool _isAdminAuthorized = true; // God Mode toggle state

  List<CiJobModel> get jobs => _jobs;
  bool get isLoading => _isLoading;
  bool get isAdminAuthorized => _isAdminAuthorized;

  // ড্যাশবোর্ডে ডাটা সিঙ্ক করা
  Future<void> syncDashboard() async {
    _isLoading = true;
    notifyListeners();

    _jobs = await _syncService.fetchLiveJobs();
    
    _isLoading = false;
    notifyListeners();
  }

  // God Mode টগল হ্যান্ডেল করা
  Future<void> toggleGodMode(bool value) async {
    final success = await _apiClient.updateGodRule('admin_authorized', value);
    if (success) {
      _isAdminAuthorized = value;
      notifyListeners();
    }
  }

  // Quick Action হ্যান্ডেল করা
  Future<bool> executeQuickAction(String actionType) async {
    return await _apiClient.triggerQuickAction(actionType);
  }
}
