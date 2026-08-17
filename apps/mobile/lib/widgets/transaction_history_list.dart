import 'package:flutter/material.dart';

class TransactionHistoryList extends StatelessWidget {
  final List<Map<String, dynamic>> history;

  const TransactionHistoryList({super.key, required this.history});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (history.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 24.0),
        child: Center(
          child: Text("No transactions recorded yet."),
        ),
      );
    }

    // বাংলা মন্তব্য: স্ক্রলেবল হিস্ট্রি লিস্ট - মাইক্রো-পেমেন্ট ও ক্রেডিট ট্র্যাকিং কার্ড।
    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: history.length,
      separatorBuilder: (ctx, idx) => const Divider(height: 1),
      itemBuilder: (ctx, idx) {
        final tx = history[idx];
        final amount = (tx["amount_usd"] as num).toDouble();
        final isCredit = amount > 0;
        final timestampStr = tx["timestamp"] ?? "";
        final time = DateTime.tryParse(timestampStr)?.toLocal() ?? DateTime.now();

        return ListTile(
          contentPadding: EdgeInsets.zero,
          leading: CircleAvatar(
            backgroundColor: isCredit ? Colors.green.withValues(alpha: 0.1) : Colors.red.withValues(alpha: 0.1),
            child: Icon(
              isCredit ? Icons.add_circle_outline : Icons.remove_circle_outline,
              color: isCredit ? Colors.green : Colors.red,
            ),
          ),
          title: Text(
            tx["description"] ?? "Transaction",
            style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          subtitle: Text(
            "${time.day}/${time.month}/${time.year} ${time.hour}:${time.minute.toString().padLeft(2, '0')}",
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          trailing: Text(
            "${isCredit ? '+' : ''}\$${amount.toStringAsFixed(4)}",
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: isCredit ? Colors.green : Colors.red,
            ),
          ),
        );
      },
    );
  }
}
