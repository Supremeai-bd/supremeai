import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

class PaymentGatewayBridge {
  /// Launches checkout workflow securely without client-side mock logic.
  /// Stripe: Triggers secure payment sheet flow or redirect checkout.
  /// SSLCommerz: Launches external browser/webview checkout URL safely.
  static Future<bool> startPaymentFlow({
    required BuildContext context,
    required String gateway,
    required String checkoutUrl,
    required double amount,
  }) async {
    // বাংলা মন্তব্য: পেমেন্ট গেটওয়ে লজিক — কোনো ক্লায়েন্ট-সাইড সিমিউলেশন বা ডামি রেজাল্ট নয়।
    if (checkoutUrl.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid payment checkout URL received.')),
      );
      return false;
    }

    final Uri uri = Uri.parse(checkoutUrl);

    if (gateway.toLowerCase() == 'stripe' || gateway.toLowerCase() == 'sslcommerz') {
      try {
        final bool launched = await launchUrl(
          uri,
          mode: LaunchMode.externalApplication,
        );
        if (!launched) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Could not open payment gateway URL: $checkoutUrl')),
          );
          return false;
        }
        return true;
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Payment initiation failed: ${e.toString()}')),
        );
        return false;
      }
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unsupported payment gateway: $gateway')),
      );
      return false;
    }
  }
}
