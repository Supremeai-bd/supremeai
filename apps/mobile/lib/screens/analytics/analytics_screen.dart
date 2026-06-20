import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';

class AnalyticsScreen extends StatelessWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: Text('analytics.title'.tr(),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('analytics.system_health'.tr().toUpperCase(), 
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)
            ),
            const SizedBox(height: 16),
            _buildMetricCard(context, 'analytics.cpu_usage'.tr(), '24%', Colors.blueAccent, Icons.memory),
            _buildMetricCard(context, 'analytics.memory_usage'.tr(), '1.2 GB / 4 GB', Colors.greenAccent, Icons.storage),
            _buildMetricCard(context, 'analytics.api_latency'.tr(), '120ms', Colors.orangeAccent, Icons.speed),
            const SizedBox(height: 32),
            Text('analytics.recent_alerts'.tr().toUpperCase(), 
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)
            ),
            const SizedBox(height: 16),
            _buildAlertTile(context, 'High Memory Warning', 'System memory usage exceeded 80%', '10 mins ago', Colors.redAccent),
            _buildAlertTile(context, 'New AI Provider Connected', 'Groq Llama-3 now available', '1 hour ago', Colors.greenAccent),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(BuildContext context, String title, String value, Color color, IconData icon) {
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
                  child: Icon(icon, color: color, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                ),
                Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w900, fontSize: 18)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAlertTile(BuildContext context, String title, String desc, String time, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.warning_rounded, color: color, size: 24),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(title, style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                      Text(time, style: const TextStyle(color: Colors.white38, fontSize: 11, fontWeight: FontWeight.w600)),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(desc, style: const TextStyle(color: Colors.white54, fontSize: 13, height: 1.4)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
