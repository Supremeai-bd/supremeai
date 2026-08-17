import 'dart:convert';
import 'api_service.dart';

class BillingService {
  final ApiService _apiService;
  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  BillingService({ApiService? apiService}) : _apiService = apiService ?? ApiService();

  /// Fetches the user's active wallet state (balance, subscription status, allowance).
  Future<Map<String, dynamic>> getWalletDetails() async {
    try {
      final token = await _apiService.getToken();
      final response = await _apiService.client.get(
        Uri.parse('$_baseUrl/api/billing/wallet'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        return {'success': true, 'wallet': jsonDecode(response.body)};
      } else {
        return {'success': false, 'error': 'Failed to load wallet balance.'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }

  /// Fetches historical transactions logged in the immutable ledger.
  /// Returns {'success': bool, 'items': List, 'error': String?} so the caller
  /// can tell "no transactions yet" apart from "the request failed" —
  /// previously both cases silently returned an empty list.
  Future<Map<String, dynamic>> getTransactionHistory() async {
    try {
      final token = await _apiService.getToken();
      final response = await _apiService.client.get(
        Uri.parse('$_baseUrl/api/billing/history'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> rawList = jsonDecode(response.body);
        return {
          'success': true,
          'items': rawList.map((e) => Map<String, dynamic>.from(e)).toList(),
        };
      }
      return {
        'success': false,
        'error': 'Failed to load transaction history.',
        'items': <Map<String, dynamic>>[],
      };
    } catch (e) {
      return {
        'success': false,
        'error': 'Connection error: $e',
        'items': <Map<String, dynamic>>[],
      };
    }
  }

  /// Triggers fund addition and returns a checkout redirect session context.
  Future<Map<String, dynamic>> initiateCheckout(double amount) async {
    try {
      final token = await _apiService.getToken();
      final response = await _apiService.client.post(
        Uri.parse('$_baseUrl/api/billing/add-funds?amount=$amount'),
        headers: {
          'Content-Type': 'application/json',
          if (token != null) 'Authorization': 'Bearer $token',
        },
      );

      final responseData = jsonDecode(response.body);
      if (response.statusCode == 200) {
        return {
          'success': true,
          'checkout_id': responseData['checkout_id'],
          'checkout_url': responseData['checkout_url']
        };
      } else {
        return {'success': false, 'error': responseData['detail'] ?? 'Checkout initialization failed.'};
      }
    } catch (e) {
      return {'success': false, 'error': 'Connection error: $e'};
    }
  }
}
