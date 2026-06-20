import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';

class ResilienceScreen extends StatelessWidget {
  const ResilienceScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('resilience.title'.tr(),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildUptimeCard(context),
            const SizedBox(height: 32),
            Text('resilience.healing_status'.tr().toUpperCase(), 
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)
            ),
            const SizedBox(height: 16),
            _buildHealingTile(context, 'Memory Leak Resolved', 'Automatic patch applied to node-04', '2h ago', Colors.greenAccent),
            _buildHealingTile(context, 'Database Failover', 'Switched to replica in us-west-1', '5h ago', Colors.orangeAccent),
            _buildHealingTile(context, 'CPU Spike Throttled', 'Rate limiting applied to guest traffic', '1d ago', Colors.blueAccent),
          ],
        ),
      ),
    );
  }

  Widget _buildUptimeCard(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        children: [
          Text('resilience.uptime'.tr().toUpperCase(), 
            style: const TextStyle(color: Colors.white38, fontSize: 12, fontWeight: FontWeight.w900, letterSpacing: 2)
          ),
          const SizedBox(height: 12),
          const Text('99.99%', 
            style: TextStyle(color: Colors.greenAccent, fontSize: 48, fontWeight: FontWeight.w900)
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.greenAccent.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.bolt, color: Colors.greenAccent, size: 16),
                const SizedBox(width: 8),
                Text('resilience.auto_recovery'.tr(), 
                  style: const TextStyle(color: Colors.greenAccent, fontWeight: FontWeight.bold, fontSize: 12)
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHealingTile(BuildContext context, String title, String desc, String time, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(Icons.health_and_safety, color: color, size: 24),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Text(desc, style: const TextStyle(color: Colors.white54, fontSize: 13)),
                    ],
                  ),
                ),
                Text(time, style: const TextStyle(color: Colors.white38, fontSize: 11)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
