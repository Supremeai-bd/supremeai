import 'package:flutter/material.dart';
import '../services/screen_api_service.dart';
import '../services/localization_service.dart';

class ApiScaffold extends StatefulWidget {
  final String screen;
  final String titleKey;
  final String emptyMessageKey;
  final Widget Function(BuildContext context, Map<String, dynamic> data, bool loading, Future<void> Function() refresh) builder;

  const ApiScaffold({
    super.key,
    required this.screen,
    required this.titleKey,
    this.emptyMessageKey = 'No data available',
    required this.builder,
  });

  @override
  State<ApiScaffold> createState() => _ApiScaffoldState();
}

class _ApiScaffoldState extends State<ApiScaffold> {
  final _api = ScreenApiService();
  bool _loading = true;
  Map<String, dynamic> _data = const <String, dynamic>{};
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _api.ping(widget.screen);
      if (!mounted) return;
      setState(() {
        _data = result;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text(widget.titleKey.tr(), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh, color: Colors.white70)),
        ],
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _data.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: Colors.blueAccent));
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
              const SizedBox(height: 16),
              Text('Failed to load ${widget.screen} data', style: const TextStyle(color: Colors.redAccent)),
              const SizedBox(height: 16),
              ElevatedButton.icon(onPressed: _load, icon: const Icon(Icons.refresh), label: Text('Retry'.tr())),
            ],
          ),
        ),
      );
    }
    return widget.builder(context, _data, _loading, _load);
  }
}
