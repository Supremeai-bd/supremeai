import 'package:flutter/material.dart';
import '../services/billing_service.dart';
import '../services/payment_gateway_bridge.dart';
import '../widgets/usage_chart.dart';
import '../widgets/transaction_history_list.dart';

class WalletScreen extends StatefulWidget {
  const WalletScreen({super.key});

  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  final BillingService _billingService = BillingService();

  Map<String, dynamic>? _wallet;
  List<Map<String, dynamic>> _history = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _refreshWallet();
  }

  Future<void> _refreshWallet() async {
    setState(() {
      _isLoading = true;
    });

    final walletRes = await _billingService.getWalletDetails();
    final historyRes = await _billingService.getTransactionHistory();

    setState(() {
      if (walletRes['success'] == true) {
        _wallet = walletRes['wallet'];
      }
      _history = List<Map<String, dynamic>>.from(historyRes['items'] ?? const []);
      _isLoading = false;
    });

    // বাংলা মন্তব্য: আগে fetch ব্যর্থ হলেও "no transactions" বলে ভুল বোঝাতো — এখন আসল এরর দেখানো হচ্ছে
    if (historyRes['success'] != true && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(historyRes['error'] ?? 'Failed to load transaction history.'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _triggerTopUp(double amount, String gateway) async {
    final checkoutRes = await _billingService.initiateCheckout(amount);
    if (checkoutRes['success'] == true) {
      final String checkoutUrl = checkoutRes['checkout_url'];

      if (mounted) {
        // Trigger multi-gateway transaction flow securely via bridge
        await PaymentGatewayBridge.startPaymentFlow(
          context: context,
          gateway: gateway,
          checkoutUrl: checkoutUrl,
          amount: amount,
        );
        // Note: The UI should ideally listen to a realtime backend stream (like WebSocket/SSE)
        // or poll for the webhook completion to update the wallet balance.
        // For now, simply refreshing the wallet manually.
        _refreshWallet();
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(checkoutRes['error'] ?? "Checkout failed."),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text("P2P Credit Dashboard"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refreshWallet,
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Wallet balance card
                  Card(
                    color: theme.colorScheme.primaryContainer,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        children: [
                          Text(
                            "Available Balance",
                            style: theme.textTheme.titleMedium?.copyWith(
                              color: theme.colorScheme.onPrimaryContainer,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            "\$${((_wallet?['balance_usd'] ?? 0.0) + (_wallet?['monthly_allowance_usd'] ?? 0.0)).toStringAsFixed(2)}",
                            style: theme.textTheme.displayMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: theme.colorScheme.onPrimaryContainer,
                            ),
                          ),
                          const SizedBox(height: 16),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                "Subscription: ${_wallet?['subscription_tier']?.toString().toUpperCase() ?? 'FREE'}",
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: theme.colorScheme.onPrimaryContainer,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Topup Actions
                  Text(
                    "Top Up Balance",
                    style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => _triggerTopUp(10.0, 'stripe'),
                          icon: const Icon(Icons.credit_card),
                          label: const Text("Stripe (+\$10)"),
                          style: ElevatedButton.styleFrom(backgroundColor: theme.colorScheme.primary, foregroundColor: Colors.white),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => _triggerTopUp(15.0, 'sslcommerz'),
                          icon: const Icon(Icons.account_balance_wallet_outlined),
                          label: const Text("MFS BDT (+\$15)"),
                          style: ElevatedButton.styleFrom(backgroundColor: Colors.pink, foregroundColor: Colors.white),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // Charts and Analytics
                  UsageChart(history: _history),
                  const SizedBox(height: 24),

                  // History Log
                  Text(
                    "Recent Transactions",
                    style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  TransactionHistoryList(history: _history),
                ],
              ),
            ),
    );
  }
}
