import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:supremeai_mobile/screens/home_screen.dart'; // Import the new home screen

void main() {
  runApp(const SupremeAIMobileApp());
}

class SupremeAIMobileApp extends StatelessWidget {
  const SupremeAIMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SupremeAI Mobile',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: const HomePage(), // Keep the original HomePage for now
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late WebSocketChannel _channel;
  final TextEditingController _textController = TextEditingController();
  final List<ChatMessage> _messages = <ChatMessage>[];
  String? _authToken;
  bool _isLoading = false;
  bool _isConnected = false;

  @override
  void initState() {
    super.initState();
    _loadAuthToken();
  }

  static const _secureStorage = FlutterSecureStorage();

  Future<void> _loadAuthToken() async {
    _authToken = await _secureStorage.read(key: 'auth_token');

    if (_authToken != null) {
      _connectWebSocket();
    }
  }

  Future<void> _connectWebSocket() async {
    if (_authToken == null) return;

    try {
      // বাংলা মন্তব্য: API_BASE_URL থেকে WebSocket URL derive করা হয়, hardcoded localhost নয়।
      // Token query-তে পাঠানো হবে না — authentication header-এ পাঠানো হবে।
      const apiBase = String.fromEnvironment(
        'API_BASE_URL',
        defaultValue: 'https://supremeai-a.web.app',
      );
      final wsBase = apiBase.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
      final wsUri = Uri.parse('$wsBase/api/ws/chat');

      // Connect without token in URL — send auth via initial message
      _channel = WebSocketChannel.connect(wsUri);
      
      // Send authentication message immediately after connection
      _channel.sink.add(jsonEncode({
        'type': 'auth',
        'token': _authToken,
      }));

      _channel.stream.listen(_handleMessage,
          onError: (error) {
            setState(() {
              _isConnected = false;
            });
            debugPrint('WebSocket error: $error');
          },
          onDone: () {
            setState(() {
              _isConnected = false;
            });
            debugPrint('WebSocket connection closed');
          });

      setState(() {
        _isConnected = true;
      });
    } catch (e) {
      debugPrint('Failed to connect WebSocket: $e');
      setState(() {
        _isConnected = false;
      });
    }
  }


  void _handleMessage(dynamic data) {
    Map<String, dynamic> jsonData = json.decode(data);

    if (jsonData['type'] == 'pong') {
      // Heartbeat response
      return;
    }

    if (jsonData.containsKey('text') || jsonData.containsKey('content')) {
      String content = jsonData['text'] ?? jsonData['content'] ?? '';

      if (content == '[DONE]') {
        setState(() {
          _isLoading = false;
        });
        return;
      }

      setState(() {
        _messages.add(ChatMessage(
          text: content,
          sender: 'ai',
        ));
        _isLoading = false;
      });
    }
  }

  Future<void> _sendMessage() async {
    if (_textController.text.isEmpty || _isLoading) return;

    String messageText = _textController.text.trim();
    _textController.clear();

    setState(() {
      _messages.add(ChatMessage(
        text: messageText,
        sender: 'user',
      ));
      _isLoading = true;
    });

    // Send message via WebSocket
    Map<String, String> message = {
      'text': messageText,
      'timestamp': DateTime.now().millisecondsSinceEpoch.toString()
    };

    _channel.sink.add(jsonEncode(message));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SupremeAI Mobile'),
        backgroundColor: Colors.blue[600],
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: Icon(_isConnected ? Icons.wifi : Icons.wifi_off),
            onPressed: () {
              if (_isConnected) {
                _channel.sink.close();
                setState(() {
                  _isConnected = false;
                });
              } else {
                _connectWebSocket();
              }
            },
          ),
          PopupMenuButton<String>(
            onSelected: (String result) {
              if (result == 'logout') {
                _logout();
              } else if (result == 'new_ui') {
                // Navigate to new UI
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => const HomeScreen()),
                );
              }
            },
            itemBuilder: (BuildContext context) => <PopupMenuEntry<String>>[
              const PopupMenuItem<String>(
                value: 'new_ui',
                child: Text('Try New UI'),
              ),
              const PopupMenuItem<String>(
                value: 'logout',
                child: Text('Logout'),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                return _messages[index];
              },
            ),
          ),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: LinearProgressIndicator(),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    decoration: const InputDecoration(
                      hintText: 'Type your message...',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send),
                  onPressed: _isLoading ? null : _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _logout() async {
    await _secureStorage.delete(key: 'auth_token');

    setState(() {
      _authToken = null;
      _isConnected = false;
      _messages.clear();
    });

    _channel.sink.close();
  }

  @override
  void dispose() {
    _channel.sink.close();
    _textController.dispose();
    super.dispose();
  }
}

class ChatMessage extends StatelessWidget {
  final String text;
  final String sender;

  const ChatMessage({
    super.key,
    required this.text,
    required this.sender,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 5.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(right: 10.0),
            child: CircleAvatar(
              backgroundColor: sender == 'user' ? Colors.blue[600] : Colors.green[600],
              child: Text(sender == 'user' ? 'U' : 'AI', style: const TextStyle(color: Colors.white)),
            ),
          ),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(10.0),
              decoration: BoxDecoration(
                color: sender == 'user' ? Colors.blue[100] : Colors.green[50],
                borderRadius: BorderRadius.circular(10.0),
              ),
              child: Text(
                text,
                style: const TextStyle(fontSize: 16.0),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
