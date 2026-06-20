import 'package:flutter/material.dart';
import '../../services/localization_service.dart';

class QuotaScreen extends StatelessWidget {
  const QuotaScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('quota.title'.tr(),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildPlanCard(context),
            const SizedBox(height: 32),
            Text('quota.current_usage'.tr().toUpperCase(), 
              style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)
            ),
            const SizedBox(height: 16),
            _buildUsageProgress(context, 'API Calls', 6500, 10000),
            const SizedBox(height: 32),
            _buildQuotaList(context),
          ],
        ),
      ),
    );
  }

  Widget _buildPlanCard(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF6366F1), Color(0xFFA855F7)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF6366F1).withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('quota.plan'.tr().toUpperCase(), 
            style: const TextStyle(color: Colors.white70, fontSize: 11, fontWeight: FontWeight.w900, letterSpacing: 2)
          ),
          const SizedBox(height: 8),
          const Text('Enterprise AI', 
            style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w900)
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const Icon(Icons.check_circle_outline, color: Colors.white70, size: 16),
              const SizedBox(width: 8),
              const Text('Priority Agent Access', style: TextStyle(color: Colors.white70, fontSize: 13)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildUsageProgress(BuildContext context, String label, int current, int total) {
    double progress = current / total;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              Text('$current / $total', style: const TextStyle(color: Colors.white38, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: Colors.white10,
              valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFFA855F7)),
              minHeight: 8,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuotaList(BuildContext context) {
    return Column(
      children: [
        _buildQuotaItem(context, 'quota.rate_limit'.tr(), '100 req / min', Icons.speed, Colors.orangeAccent),
        _buildQuotaItem(context, 'quota.max_projects'.tr(), 'Unlimited', Icons.inventory_2_outlined, Colors.greenAccent),
        _buildQuotaItem(context, 'quota.concurrent_agents'.tr(), '50 Active', Icons.bolt, Colors.blueAccent),
      ],
    );
  }

  Widget _buildQuotaItem(BuildContext context, String title, String value, IconData icon, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.02),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 16),
          Expanded(child: Text(title, style: const TextStyle(color: Colors.white, fontSize: 14))),
          Text(value, style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold, fontSize: 14)),
        ],
      ),
    );
  }
}
