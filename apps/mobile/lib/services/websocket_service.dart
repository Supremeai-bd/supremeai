// apps/mobile/lib/services/websocket_service.dart
import 'dart:async';
import 'dart:io';

class WebSocketService {
  WebSocket? _ws;
  final String _url;
  final String _token;
  int _retryCount = 0;
  Timer? _reconnectTimer;
  final _controller = StreamController<String>.broadcast();
  final _pending = <String>[];
  static const _maxRetries = 10;

  WebSocketService({required String url, required String token})
      : _url = url,
        _token = token;

  Stream<String> get messages => _controller.stream;

  Future<void> connect() async {
    try {
      _ws = await WebSocket.connect(_url);
      _ws!.add(_token); // auth handshake
      _retryCount = 0;
      _ws!.listen(
        (data) => _controller.add(data.toString()),
        onDone: _scheduleReconnect,
        onError: (_) => _scheduleReconnect(),
      );
      while (_pending.isNotEmpty) {
        _ws!.add(_pending.removeAt(0));
      }
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_retryCount >= _maxRetries) return;
    final delay = Duration(seconds: 1 << _retryCount);
    _retryCount++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, connect);
  }

  void send(String msg) {
    if (_ws != null && _ws!.readyState == WebSocket.open) {
      _ws!.add(msg);
    } else {
      _pending.add(msg);
    }
  }

  void dispose() {
    _reconnectTimer?.cancel();
    _ws?.close();
    _controller.close();
  }
}
