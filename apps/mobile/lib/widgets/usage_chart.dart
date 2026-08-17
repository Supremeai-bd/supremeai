import 'package:flutter/material.dart';

class UsageChart extends StatelessWidget {
  final List<Map<String, dynamic>> history;

  const UsageChart({super.key, required this.history});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Group usage by model (simulating backend aggregations)
    // বাংলা মন্তব্য: কস্ট সামারি এগ্রিগেশন - মডেল ভিত্তিক ক্রেডিট ইউসেজ চার্ট হিস্ট্রি।
    final Map<String, double> usageByModel = {};
    for (var tx in history) {
      if (tx["transaction_type"] == "token_usage") {
        final desc = tx["description"] as String;
        final parts = desc.split("model: ");
        final model = parts.length > 1 ? parts[1] : "other";
        final cost = (tx["amount_usd"] as num).toDouble().abs();
        usageByModel[model] = (usageByModel[model] ?? 0.0) + cost;
      }
    }

    if (usageByModel.isEmpty) {
      return Container(
        height: 150,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Text("No token consumption records found for this period."),
      );
    }

    return Card(
      elevation: 0,
      color: theme.colorScheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "Credit Spent by Model",
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            ...usageByModel.entries.map((entry) {
              final model = entry.key;
              final spent = entry.value;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6.0),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(model, style: theme.textTheme.bodyMedium),
                        Text(
                          "\$${spent.toStringAsFixed(4)}",
                          style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: (spent * 10).clamp(0.01, 1.0), // Scale factor for presentation
                        backgroundColor: theme.colorScheme.outlineVariant,
                        color: theme.colorScheme.primary,
                        minHeight: 8,
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
