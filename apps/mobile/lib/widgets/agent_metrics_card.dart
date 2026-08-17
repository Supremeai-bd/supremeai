// apps/mobile/lib/widgets/agent_metrics_card.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/orchestration_provider.dart';

class AgentMetricsCard extends StatelessWidget {
  const AgentMetricsCard({super.key});

  @override
  Widget build(BuildContext context) {
    // আমাদের সিঙ্ক করা OrchestrationProvider ওয়াচ করা হচ্ছে
    return Consumer<OrchestrationProvider>(
      builder: (context, provider, child) {
        final metrics = provider.activeAgentMetrics;
        final executionTier = metrics['execution_tier'] ?? 'Idle';
        final isZeroCost = executionTier.contains('Layer 2');
        final extractedNodes = (metrics['data'] is Map) ? (metrics['data'] as Map).length : 0;
        final latencyMs = metrics['latency_ms'] ?? '0';
        final agentStatus = metrics['status'] ?? 'idle';
        final activeTasks = metrics['active_tasks'] ?? 0;
        final cpuUsage = metrics['cpu_usage'] ?? '0%';
        final memoryUsage = metrics['memory_usage'] ?? '0%';

        return Card(
          elevation: 4,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          color: isZeroCost ? Colors.teal.shade900 : Colors.indigo.shade900,
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      "Active Agent State",
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: isZeroCost ? Colors.greenAccent.shade400 : Colors.orangeAccent,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        isZeroCost ? "ZERO COST" : "API ACTIVE",
                        style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 12),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  executionTier,
                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),
                const Divider(color: Colors.white24),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildStatNode("Extracted Nodes", "$extractedNodes"),
                    _buildStatNode("Latency Guard", "${latencyMs}ms"),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _buildStatNode("Active Tasks", "$activeTasks"),
                    _buildStatNode("CPU", "$cpuUsage"),
                  ],
                ),
                const SizedBox(height: 12),
                _buildProgressBar("Memory Usage", double.tryParse(memoryUsage.replaceAll('%', '')) ?? 0.0),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildStatNode(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.white60, fontSize: 12)),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildProgressBar(String label, double value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(color: Colors.white60, fontSize: 12)),
            Text('$value%', style: const TextStyle(color: Colors.white, fontSize: 12)),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: value / 100,
          backgroundColor: Colors.grey[800],
          valueColor: AlwaysStoppedAnimation<Color>(
            value > 80 ? Colors.red : value > 60 ? Colors.orange : Colors.green,
          ),
        ),
      ],
    );
  }
}
