// apps/mobile/lib/screens/quota/quota_screen.dart
// Production Quota Management Screen for SupremeAI Flutter Mobile
// বাংলা মন্তব্য: টোকেন ইউসেজ ও এআই মডেল কোটা মনিটরিং স্ক্রিন।

import 'package:flutter/material.dart';

class QuotaScreen extends StatelessWidget {
  const QuotaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F172A),
        elevation: 0,
        title: const Text(
          'API Quota & Usage',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Daily Execution Progress Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.cyan.withValues(alpha: 0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Daily Free Executions',
                        style: TextStyle(color: Color(0xFFCBD5E1), fontSize: 14),
                      ),
                      Text(
                        '342 / 500 Used',
                        style: TextStyle(color: Colors.cyan, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  LinearProgressIndicator(
                    value: 0.68,
                    backgroundColor: const Color(0xFF1E293B),
                    valueColor: const AlwaysStoppedAnimation<Color>(Colors.cyan),
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Resets in 6h 18m • Zero-Cost Optimization Active',
                    style: TextStyle(color: Color(0xFF64748B), fontSize: 11),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            const Text(
              'Provider Quota Breakdown',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),

            _buildProviderTile('DeepSeek-V3', 'Coding & Math', 0.45, Colors.purpleAccent),
            _buildProviderTile('Kimi K2.5', 'Bangla & Reasoning', 0.30, Colors.cyan),
            _buildProviderTile('Together AI', 'Auto-Fallback Engine', 0.10, Colors.amber),
          ],
        ),
      ),
    );
  }

  Widget _buildProviderTile(String name, String role, double usage, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: color.withValues(alpha: 0.2),
            child: Icon(Icons.memory, color: color),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                ),
                Text(
                  role,
                  style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                ),
              ],
            ),
          ),
          Text(
            '${(usage * 100).toInt()}%',
            style: TextStyle(color: color, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }
}
