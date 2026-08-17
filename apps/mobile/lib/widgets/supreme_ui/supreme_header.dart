import 'package:flutter/material.dart';
import '../../theme/tokens.dart';

class SupremeHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final bool gradient;

  const SupremeHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.gradient = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (gradient)
          ShaderMask(
            shaderCallback: (bounds) => const LinearGradient(
              colors: [DesignTokens.colorBrandPrimaryDark, DesignTokens.colorBrandSecondaryDark],
            ).createShader(bounds),
            child: Text(
              title,
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.white,
                letterSpacing: 1.2,
              ),
            ),
          )
        else
          Text(
            title,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: DesignTokens.colorTextPrimaryDark,
              letterSpacing: 1.2,
            ),
          ),
        if (subtitle != null) ...[
          const SizedBox(height: 8),
          Text(
            subtitle!,
            style: const TextStyle(
              fontSize: 14,
              color: DesignTokens.colorTextSecondaryDark,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ],
    );
  }
}
