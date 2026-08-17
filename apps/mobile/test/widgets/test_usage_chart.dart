import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:supremeai_mobile/widgets/usage_chart.dart';

void main() {
  Widget createUsageChart({List<Map<String, dynamic>>? history}) {
    return MaterialApp(
      home: Scaffold(
        body: UsageChart(history: history ?? const []),
      ),
    );
  }

  testWidgets('UsageChart shows empty state when history is empty', (WidgetTester tester) async {
    await tester.pumpWidget(createUsageChart());
    await tester.pumpAndSettle();

    expect(find.text('No token consumption records found for this period.'), findsOneWidget);
  });

  testWidgets('UsageChart shows empty state when no token_usage transactions', (WidgetTester tester) async {
    final history = [
      {"transaction_type": "credit_purchase", "amount_usd": 10.0, "description": "top-up"},
    ];
    await tester.pumpWidget(createUsageChart(history: history));
    await tester.pumpAndSettle();

    expect(find.text('No token consumption records found for this period.'), findsOneWidget);
  });

  testWidgets('UsageChart aggregates spending by model', (WidgetTester tester) async {
    final history = [
      {"transaction_type": "token_usage", "amount_usd": 0.05, "description": "model: gpt-4o"},
      {"transaction_type": "token_usage", "amount_usd": 0.01, "description": "model: gpt-4o"},
      {"transaction_type": "token_usage", "amount_usd": 0.02, "description": "model: claude-3"},
    ];
    await tester.pumpWidget(createUsageChart(history: history));
    await tester.pumpAndSettle();

    expect(find.text('gpt-4o'), findsOneWidget);
    expect(find.text('\$0.0600'), findsOneWidget);
    expect(find.text('claude-3'), findsOneWidget);
    expect(find.text('\$0.0200'), findsOneWidget);
  });

  testWidgets('UsageChart handles other model when description has no model prefix', (WidgetTester tester) async {
    final history = [
      {"transaction_type": "token_usage", "amount_usd": 0.10, "description": "raw usage"},
    ];
    await tester.pumpWidget(createUsageChart(history: history));
    await tester.pumpAndSettle();

    expect(find.text('other'), findsOneWidget);
    expect(find.text('\$0.1000'), findsOneWidget);
  });

  testWidgets('UsageChart accumulates multiple models independently', (WidgetTester tester) async {
    final history = [
      {"transaction_type": "token_usage", "amount_usd": 1.5, "description": "model: gemini-2.5"},
      {"transaction_type": "token_usage", "amount_usd": 2.0, "description": "model: gemini-2.5"},
      {"transaction_type": "token_usage", "amount_usd": 0.5, "description": "model: gemini-2.5-pro"},
    ];
    await tester.pumpWidget(createUsageChart(history: history));
    await tester.pumpAndSettle();

    expect(find.text('\$3.5000'), findsOneWidget);
    expect(find.text('\$0.5000'), findsOneWidget);
  });
}
