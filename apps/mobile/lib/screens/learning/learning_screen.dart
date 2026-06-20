import 'package:flutter/material.dart';
import '../../services/localization_service.dart';

class LearningScreen extends StatelessWidget {
  const LearningScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 120,
            floating: true,
            pinned: true,
            backgroundColor: Colors.black,
            flexibleSpace: FlexibleSpaceBar(
              title: Text('learning.matrix'.tr().toUpperCase(), 
                style: const TextStyle(
                  fontSize: 12, 
                  fontWeight: FontWeight.w900, 
                  letterSpacing: 2,
                  color: Colors.white
                )
              ),
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
Colors.tealAccent.withValues(alpha: 0.1),
                      Colors.black,
                    ],
                  ),
                ),
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.all(16),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                _buildSectionHeader('learning.evolution_status'.tr()),
                const SizedBox(height: 12),
                _buildStatusCard(context),
                const SizedBox(height: 24),
                _buildSectionHeader('learning.skills_training'.tr()),
                const SizedBox(height: 12),
                _buildSkillItem('Supreme-Coder-V2', 0.85, 'Mastering Flutter/Dart optimization patterns', Colors.blue),
                _buildSkillItem('Bengali-OCR-Pro', 0.94, 'Refining handwritten script recognition', Colors.pink),
                _buildSkillItem('Nexus-Reverse-Eng', 0.62, 'Analyzing obfuscated API structures', Colors.orange),
                const SizedBox(height: 24),
                _buildSectionHeader('learning.evolution_controls'.tr()),
                const SizedBox(height: 12),
                _buildControlTile('Autonomous Growth', 'Allow system to initiate research', true),
                _buildControlTile('Neural Sync', 'Synchronize cross-agent knowledge', false),
                const SizedBox(height: 40),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title.toUpperCase(),
      style: const TextStyle(
        color: Colors.white38,
        fontSize: 10,
        fontWeight: FontWeight.bold,
        letterSpacing: 1.5,
      ),
    );
  }

  Widget _buildStatusCard(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('learning.strategy'.tr().toUpperCase(), style: const TextStyle(color: Colors.white30, fontSize: 9, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text('AGGRESSIVE_EVOLVE', style: TextStyle(color: Colors.tealAccent.shade400, fontWeight: FontWeight.w900, fontSize: 16)),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.tealAccent.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text('OPTIMAL', style: TextStyle(color: Colors.tealAccent, fontSize: 9, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
          const Divider(height: 32, color: Colors.white10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildMetric('94.8%', 'learning.confidence'.tr()),
              _buildMetric('1,245', 'learning.knowledge_nodes'.tr()),
              _buildMetric('89', 'learning.skills_mastered'.tr()),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String value, String label) {
    return Column(
      children: [
        Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18)),
        const SizedBox(height: 4),
        Text(label.toUpperCase(), style: const TextStyle(color: Colors.white24, fontSize: 8, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildSkillItem(String name, double progress, String detail, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.02),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
              Text('${(progress * 100).toInt()}%', style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: progress,
            backgroundColor: Colors.white.withValues(alpha: 0.05),
            color: color,
            minHeight: 2,
          ),
          const SizedBox(height: 8),
          Text(detail, style: const TextStyle(color: Colors.white38, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildControlTile(String title, String subtitle, bool value) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.02),
        borderRadius: BorderRadius.circular(12),
      ),
      child: SwitchListTile(
        title: Text(title, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
        subtitle: Text(subtitle, style: const TextStyle(color: Colors.white24, fontSize: 10)),
        value: value,
        onChanged: (val) {},
        activeThumbColor: Colors.tealAccent,
      ),
    );
  }
}
