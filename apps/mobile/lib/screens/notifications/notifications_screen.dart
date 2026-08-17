// apps/mobile/lib/screens/notifications/notifications_screen.dart
// Production Notifications Screen for SupremeAI Flutter Mobile
// বাংলা মন্তব্য: সিস্টেম ও অটোনোমাস এজেন্ট নোটিফিকেশন প্রদর্শন ও ফিল্টারিং স্ক্রিন।

import 'package:flutter/material.dart';

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final notifications = [
      {
        'title': 'Autonomous Healer Triggered',
        'subtitle': 'Circuit breaker successfully prevented downtime on Swarm service.',
        'time': '2m ago',
        'type': 'success',
      },
      {
        'title': 'DeepSeek-V3 Model Quota Warning',
        'subtitle': 'Daily quota has reached 75%. Fallback routing ready.',
        'time': '1h ago',
        'type': 'warning',
      },
      {
        'title': 'JIT OTP Security Shield Active',
        'subtitle': 'New IP detected for admin session. OTP verified.',
        'time': '3h ago',
        'type': 'info',
      },
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F172A),
        elevation: 0,
        title: const Text(
          'Notifications',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: notifications.length,
        itemBuilder: (context, index) {
          final notif = notifications[index];
          return Card(
            color: const Color(0xFF1E293B),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            margin: const EdgeInsets.only(bottom: 12),
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              leading: CircleAvatar(
                backgroundColor: notif['type'] == 'success'
                    ? const Color(0xFF10B981).withValues(alpha: 0.2)
                    : notif['type'] == 'warning'
                        ? Colors.green.withValues(alpha: 0.2)
                        : Colors.cyan.withValues(alpha: 0.2),
                child: Icon(
                  notif['type'] == 'success'
                      ? Icons.check_circle_outline
                      : notif['type'] == 'warning'
                          ? Icons.warning_amber_rounded
                          : Icons.shield_outlined,
                  color: notif['type'] == 'success'
                      ? const Color(0xFF10B981)
                      : notif['type'] == 'warning'
                          ? Colors.amber
                          : Colors.cyan,
                ),
              ),
              title: Text(
                notif['title']!,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  notif['subtitle']!,
                  style: TextStyle(color: Colors.grey[300], fontSize: 12),
                ),
              ),
              trailing: Text(
                notif['time']!,
                style: const TextStyle(color: Color(0xFF64748B), fontSize: 10),
              ),
            ),
          );
        },
      ),
    );
  }
}
