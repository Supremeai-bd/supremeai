import 'package:flutter/material.dart';

class ChatMessage extends StatelessWidget {
  final String text;
  final String sender;
  final bool isMe;

  const ChatMessage({
    super.key,
    required this.text,
    required this.sender,
    required this.isMe,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 5.0, horizontal: 8.0),
      child: Row(
        mainAxisAlignment: isMe ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isMe) ...[
            CircleAvatar(
              radius: 18,
              backgroundColor: const Color(0xFF2563EB),
              child: Text(
                sender[0],
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(12.0),
              decoration: BoxDecoration(
                color: isMe ? const Color(0xFF2563EB) : const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: !isMe ? const Radius.circular(4) : const Radius.circular(18),
                  bottomRight: isMe ? const Radius.circular(4) : const Radius.circular(18),
                ),
              ),
              child: Text(
                text,
                style: TextStyle(
                  color: isMe ? Colors.white : const Color(0xFF334155),
                  fontSize: 16,
                ),
              ),
            ),
          ),
          if (isMe) ...[
            const SizedBox(width: 8),
            const CircleAvatar(
              radius: 18,
              backgroundColor: Color(0xFF10B981),
              child: Text(
                'U',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}