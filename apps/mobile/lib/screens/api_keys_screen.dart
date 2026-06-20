import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:ui';
import '../providers/auth_provider.dart';
import '../services/localization_service.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ApiKeysScreen extends StatefulWidget {
  const ApiKeysScreen({super.key});

  @override
  State<ApiKeysScreen> createState() => _ApiKeysScreenState();
}

class _ApiKeysScreenState extends State<ApiKeysScreen> {
  List<Map<String, dynamic>> _apiKeys = [];
  bool _isLoading = true;

  static const String _baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://supremeai-a.web.app',
  );

  @override
  void initState() {
    super.initState();
    _loadApiKeys();
  }

  Future<void> _loadApiKeys() async {
    final auth = context.read<AuthProvider>();
    if (auth.token == null) return;

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/apikeys'),
        headers: {
          'Authorization': 'Bearer ${auth.token}',
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        setState(() {
          _apiKeys = List<Map<String, dynamic>>.from(data);
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _testSingleKey(String id) async {
    final auth = context.read<AuthProvider>();
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/apikeys/$id/test'),
        headers: {'Authorization': 'Bearer ${auth.token}'},
      );
      if (response.statusCode == 200) {
        final result = json.decode(response.body);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(result['message'] ?? 'api_keys.test_success'.tr())),
        );
        _loadApiKeys();
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('error.server'.tr())),
      );
    }
  }

  Future<void> _testAllKeys() async {
    final auth = context.read<AuthProvider>();
    setState(() => _isLoading = true);
    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/api/apikeys/test-all'),
        headers: {'Authorization': 'Bearer ${auth.token}'},
      );
      if (response.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('api_keys.validation_triggered'.tr())),
        );
        _loadApiKeys();
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('error.server'.tr())),
      );
      setState(() => _isLoading = false);
    }
  }

  Future<void> _deleteApiKey(String id) async {
    final auth = context.read<AuthProvider>();
    try {
      await http.delete(
        Uri.parse('$_baseUrl/api/apikeys/$id'),
        headers: {'Authorization': 'Bearer ${auth.token}'},
      );
      _loadApiKeys();
    } catch (e) {
      // Error
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        flexibleSpace: ClipRect(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
            child: Container(color: Colors.black.withValues(alpha: 0.5)),
          ),
        ),
        title: Text('api_keys.title'.tr().toUpperCase(),
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white)
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.bolt, color: Colors.blueAccent),
            tooltip: 'Test All Active',
            onPressed: _testAllKeys,
          ),
        ],
      ),
      body: Container(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: Alignment.topRight,
            radius: 1.5,
            colors: [Colors.purpleAccent.withValues(alpha: 0.1), Colors.black],
          ),
        ),
        child: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.blueAccent))
          : _apiKeys.isEmpty
            ? Center(child: Text('api_keys.empty'.tr(), style: const TextStyle(color: Colors.white38)))
            : ListView.builder(
                padding: const EdgeInsets.fromLTRB(16, 120, 16, 16),
                itemCount: _apiKeys.length,
                itemBuilder: (context, index) {
                  final apiKey = _apiKeys[index];
                  final status = apiKey['status'] ?? 'unknown';
                  return _buildKeyCard(apiKey, status);
                },
              ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
        backgroundColor: Colors.blueAccent,
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildKeyCard(Map<String, dynamic> apiKey, String status) {
    final isActive = status == 'active';
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.05),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
            ),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: (isActive ? Colors.green : Colors.red).withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    isActive ? Icons.check_circle_outline : Icons.error_outline,
                    color: isActive ? Colors.greenAccent : Colors.redAccent,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(apiKey['label'] ?? apiKey['provider'],
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)
                      ),
                      const SizedBox(height: 4),
                      Text('${'status.working'.tr()}: ${status.toUpperCase()}',
                        style: TextStyle(color: Colors.white.withValues(alpha: 0.5), fontSize: 12)
                      ),
                    ],
                  ),
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.science_outlined, color: Colors.blueAccent),
                      onPressed: () => _testSingleKey(apiKey['id']),
                    ),
                    IconButton(
                      icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                      onPressed: () => _deleteApiKey(apiKey['id']),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

