// apps/mobile/lib/models/agent_metrics.dart

class AgentMetrics {
  final double cost;
  final int latencyMs;
  final String executionTier;
  final Map<String, dynamic> data;

  AgentMetrics({
    required this.cost,
    required this.latencyMs,
    required this.executionTier,
    required this.data,
  });

  factory AgentMetrics.fromMap(Map<String, dynamic> map) {
    return AgentMetrics(
      // সরাসরি double-এ কাস্ট না করে প্রথমে 'num' হিসেবে রিড করে .toDouble() করা বুলেটপ্রুফ সেফ
      cost: (map['cost'] as num?)?.toDouble() ?? 0.0,
      latencyMs: map['latency_ms'] as int? ?? 0,
      executionTier: map['execution_tier'] as String? ?? 'Unknown',
      data: map['data'] as Map<String, dynamic>? ?? {},
    );
  }
}
