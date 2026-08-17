// apps/mobile/lib/widgets/live_execution_logger.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/orchestration_provider.dart';

class LiveExecutionLogger extends StatelessWidget {
  const LiveExecutionLogger({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<OrchestrationProvider>(
      builder: (context, provider, child) {
        final logs = provider.activeAgentMetrics['steps_log'] as List<dynamic>? ?? [];

        if (logs.isEmpty) {
          return const Center(
            child: Text("No automation tasks currently running.", style: TextStyle(color: Colors.grey)),
          );
        }

        return ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: logs.length,
          itemBuilder: (context, index) {
            final log = logs[index];
            final status = log['status'] ?? 'pending';

            return ListTile(
              leading: CircleAvatar(
                backgroundColor: _getStatusColor(status),
                radius: 6,
              ),
              title: Text(
                "${log['action'].toString().toUpperCase()} -> ${log['selector'] ?? ''}",
                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
              ),
              subtitle: Text("Delay: ${log['simulated_delay'] ?? '0'}ms"),
              trailing: Text(
                status,
                style: TextStyle(color: _getStatusTextColor(status), fontSize: 12),
              ),
            );
          },
        );
      },
    );
  }

  Color _getStatusColor(String status) {
    if (status == 'success') return Colors.green;
    if (status == 'running') return Colors.blue;
    return Colors.grey;
  }

  Color _getStatusTextColor(String status) {
    if (status == 'success') return Colors.green.shade700;
    if (status == 'running') return Colors.blue.shade700;
    return Colors.black54;
  }
}
