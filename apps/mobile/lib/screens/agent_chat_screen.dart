import 'package:flutter/material.dart';
import '../services/neural_stream_service.dart';

class AgentChatScreen extends StatefulWidget {
  const AgentChatScreen({Key? key}) : super(key: key);

  @override
  _AgentChatScreenState createState() => _AgentChatScreenState();
}

class _AgentChatScreenState extends State<AgentChatScreen> {
  final NeuralStreamService _wsService = NeuralStreamService();
  final TextEditingController _controller = TextEditingController();
  
  List<Map<String, String>> _messages = [];
  String _currentStream = "";
  bool _isGenerating = false;

  @override
  void initState() {
    super.initState();
    _wsService.connect();
    
    // WebSocket স্ট্রিম শোনা
    _wsService.stream.listen((data) {
      if (data == '[DONE]') {
        setState(() {
          _messages.add({"role": "assistant", "content": _currentStream});
          _currentStream = "";
          _isGenerating = false;
        });
      } else {
        setState(() {
          _currentStream += data; // লাইভ টাইপিং ইফেক্ট
        });
      }
    });
  }

  void _sendMessage() {
    if (_controller.text.isEmpty || _isGenerating) return;
    
    setState(() {
      _messages.add({"role": "user", "content": _controller.text});
      _isGenerating = true;
    });
    
    _wsService.sendMessage(_controller.text);
    _controller.clear();
  }

  @override
  void dispose() {
    _wsService.disconnect();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF080B12),
      appBar: AppBar(title: const Text('Neural Agent'), backgroundColor: const Color(0xFF111827)),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length + (_isGenerating ? 1 : 0),
              itemBuilder: (context, index) {
                if (index == _messages.length && _isGenerating) {
                  // লাইভ স্ট্রিম হচ্ছে এমন বাবল
                  return _buildBubble("assistant", _currentStream);
                }
                final msg = _messages[index];
                return _buildBubble(msg["role"]!, msg["content"]!);
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: "Ask agent to check system health...",
                      hintStyle: const TextStyle(color: Colors.grey),
                      filled: true,
                      fillColor: const Color(0xFF1F2937),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send, color: Colors.blueAccent),
                  onPressed: _sendMessage,
                )
              ],
            ),
          )
        ],
      ),
    );
  }

  Widget _buildBubble(String role, String text) {
    bool isUser = role == "user";
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isUser ? Colors.blueAccent : const Color(0xFF1F2937),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(text, style: const TextStyle(color: Colors.white)),
      ),
    );
  }
}
