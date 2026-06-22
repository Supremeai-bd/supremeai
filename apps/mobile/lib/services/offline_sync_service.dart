import 'dart:convert';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;

class QueuedRequest {
  final String method;
  final String path;
  final Map<String, dynamic> body;
  final DateTime queuedAt;

  QueuedRequest({
    required this.method,
    required this.path,
    this.body = const {},
    required this.queuedAt,
  });

  Map<String, dynamic> toJson() => {
        "method": method,
        "path": path,
        "body": body,
        "queued_at": queuedAt.toIso8601String(),
      };

  factory QueuedRequest.fromJson(Map<String, dynamic> json) => QueuedRequest(
        method: json["method"] as String,
        path: json["path"] as String,
        body: json["body"] as Map<String, dynamic>,
        queuedAt: DateTime.parse(json["queued_at"] as String),
      );
}

class OfflineSyncService {
  static final OfflineSyncService _instance = OfflineSyncService._internal();
  factory OfflineSyncService() => _instance;
  OfflineSyncService._internal();

  final Connectivity _connectivity = Connectivity();
  final List<QueuedRequest> _queue = [];
  bool _isOnline = true;

  Future<void> initialize() async {
    await _loadQueue();
    final result = await _connectivity.checkConnectivity();
    _isOnline = result.any((c) => c != ConnectivityResult.none);
  }

  Future<void> _loadQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList('offline_queue') ?? [];
    _queue.clear();
    for (final item in raw) {
      _queue.add(QueuedRequest.fromJson(jsonDecode(item) as Map<String, dynamic>));
    }
  }

  Future<void> _persistQueue() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = _queue.map((r) => jsonEncode(r.toJson())).toList();
    await prefs.setStringList('offline_queue', raw);
  }

  Future<http.Response> send(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Map<String, dynamic>? body,
  }) async {
    final payload = body ?? <String, dynamic>{};

    if (_isOnline) {
      final response = await http.send(
        http.Request(method, uri)
          ..headers.addAll(headers ?? {})
          ..body = jsonEncode(payload),
      );
      if (response.statusCode >= 200 && response.statusCode < 400) {
        await _flushQueue();
        return http.Response.fromStream(response);
      }
    }

    final queued = QueuedRequest(
      method: method,
      path: uri.toString(),
      body: payload,
      queuedAt: DateTime.now(),
    );
    _queue.add(queued);
    await _persistQueue();
    return http.Response('{"status":"queued_offline"}', 202, headers: {"Content-Type": "application/json"});
  }

  Future<void> _flushQueue() async {
    if (_queue.isEmpty) return;
    final pending = List<QueuedRequest>.from(_queue);
    _queue.clear();
    await _persistQueue();
    for (final req in pending) {
      try {
        final uri = Uri.parse(req.path);
        final response = await http.send(
          http.Request(req.method, uri)
            ..headers.addAll({"Content-Type": "application/json"})
            ..body = jsonEncode(req.body),
        );
        if (response.statusCode < 200 || response.statusCode >= 400) {
          _queue.add(req);
        }
      } catch (_) {
        _queue.add(req);
      }
    }
    await _persistQueue();
  }

  Future<void> checkConnectivity() async {
    final result = await _connectivity.checkConnectivity();
    final wasOffline = !_isOnline;
    _isOnline = result.any((c) => c != ConnectivityResult.none);
    if (wasOffline && _isOnline) {
      await _flushQueue();
    }
  }
}
