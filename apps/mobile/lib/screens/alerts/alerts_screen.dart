import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';

class AlertsScreen extends StatelessWidget {
  const AlertsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('alerts.title'.tr().toUpperCase(),
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white)
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildAlertCard(
            context, 
            'alerts.rate_limit'.tr(), 
            'alerts.quota_exceeded'.tr(), 
            '5m ago', 
            Colors.redAccent, 
            Icons.error_outline
          ),
          _buildAlertCard(
            context, 
            'alerts.slow_response'.tr(), 
            'alerts.high_latency'.tr(), 
            '12m ago', 
            Colors.orangeAccent, 
            Icons.warning_amber_rounded
          ),
          _buildAlertCard(
            context, 
            'projects.status'.tr(), 
            'Synchronized 1.2k records with Firestore replica.', 
            '1h ago', 
            Colors.greenAccent, 
            Icons.check_circle_outline
          ),
        ],
      ),
    );
  }

  Widget _buildAlertCard(BuildContext context, String title, String desc, String time, Color color, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(icon, color: color, size: 24),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(title, style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
                          Text(time, style: const TextStyle(color: Colors.white38, fontSize: 11)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(desc, style: const TextStyle(color: Colors.white54, fontSize: 13, height: 1.4)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
