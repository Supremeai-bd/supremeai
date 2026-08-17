import 'package:flutter/material.dart';
import '../../theme/tokens.dart';

class SupremeCard extends StatelessWidget {
  final Widget child;
  final bool glow;
  final EdgeInsetsGeometry? padding;

  const SupremeCard({
    super.key,
    required this.child,
    this.glow = false,
    this.padding,
  });

  @override
  Widget build(BuildContext context) {
    // MediaQuery for responsive padding
    final screenWidth = MediaQuery.of(context).size.width;
    final defaultPadding = screenWidth > 600 ? const EdgeInsets.all(24.0) : const EdgeInsets.all(16.0);

    return Container(
      padding: padding ?? defaultPadding,
      decoration: BoxDecoration(
        color: DesignTokens.colorBgElevatedDark,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: DesignTokens.colorBorderAccentDark,
          width: 1,
        ),
        boxShadow: glow
            ? [
                BoxShadow(
                  color: DesignTokens.colorBrandPrimaryDark.withValues(alpha: 0.4),
                  blurRadius: 15,
                  spreadRadius: 2,
                )
              ]
            : [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 20,
                  offset: const Offset(0, 4),
                )
              ],
      ),
      child: child,
    );
  }
}
