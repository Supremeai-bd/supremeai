import 'package:flutter/material.dart';
import 'dart:ui';
import '../../services/localization_service.dart';

class GitScreen extends StatelessWidget {
  const GitScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('git.title'.tr(),
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.sync, color: Colors.blueAccent),
            onPressed: () {},
          ),
        ],
      ),
      body: Stack(
        children: [
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 300,
              height: 300,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.blueAccent.withValues(alpha: 0.05),
              ),
            ),
          ),
          ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _buildHeaderCard(context),
              const SizedBox(height: 32),
              Text('git.recent_commits'.tr().toUpperCase(), 
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54)
              ),
              const SizedBox(height: 16),
              _buildCommitTile(context, 'Automated PR #42: Feature Sync', 'Merged by Architect-Agent', '15m ago', Icons.merge_type, Colors.purpleAccent),
              _buildCommitTile(context, 'Branch: feature/ai-consensus', 'Updated model voting logic', '1h ago', Icons.history, Colors.blueAccent),
              _buildCommitTile(context, 'Hotfix: API rate limit', 'In-memory fallback implemented', '3h ago', Icons.bug_report_outlined, Colors.orangeAccent),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderCard(BuildContext context) {
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
          const Icon(Icons.commit, color: Colors.orangeAccent, size: 48),
          const SizedBox(height: 16),
          Text('git.subtitle'.tr(), 
            style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text('git.description'.tr(), 
            style: const TextStyle(color: Colors.white54, fontSize: 13, height: 1.5),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildMetric('main', 'git.active_branch'.tr()),
              _buildMetric('156', 'git.commit'.tr()),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String value, String label) {
    return Column(
      children: [
        Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 16)),
        const SizedBox(height: 4),
        Text(label.toUpperCase(), style: const TextStyle(color: Colors.white24, fontSize: 9, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildCommitTile(BuildContext context, String title, String subtitle, String time, IconData icon, Color color) {
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
                  child: Icon(icon, color: color, size: 24),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Text(subtitle, style: const TextStyle(color: Colors.white38, fontSize: 12)),
                    ],
                  ),
                ),
                Text(time, style: const TextStyle(color: Colors.white24, fontSize: 10)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
