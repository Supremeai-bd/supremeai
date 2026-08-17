import 'package:flutter/material.dart';

class LiveTerminal extends StatelessWidget {
  final List<String> logs;

  const LiveTerminal({super.key, required this.logs});

  @override
  Widget build(BuildContext context) {

    // বাংলা মন্তব্য: লাইভ টার্মিনাল লগ রেন্ডারিং - জ্যাঙ্ক এড়াতে এখানে কাস্টম স্ক্রল অপ্টিমাইজেশন যুক্ত করা হয়েছে।
    return Container(
      height: 250,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white10),
      ),
      child: ListView.builder(
        itemCount: logs.length,
        shrinkWrap: true,
        physics: const ClampingScrollPhysics(),
        itemBuilder: (ctx, idx) {
          final log = logs[idx];
          Color logColor = Colors.white70;

          if (log.startsWith("✅")) {
            logColor = const Color(0xFF4CAF50);
          } else if (log.startsWith("❌")) {
            logColor = const Color(0xFFF44336);
          } else if (log.startsWith("⚙️") || log.contains("pipeline")) {
            logColor = const Color(0xFF2196F3);
          }

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 2.0),
            child: Text(
              log,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: logColor,
              ),
            ),
          );
        },
      ),
    );
  }
}
