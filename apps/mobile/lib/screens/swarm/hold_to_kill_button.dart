import 'package:flutter/material.dart';
import '../../theme/tokens.dart'; // Adjust path to your generated DesignTokens

class HoldToKillButton extends StatefulWidget {
  final VoidCallback onTrigger;

  const HoldToKillButton({super.key, required this.onTrigger});

  @override
  State<HoldToKillButton> createState() => _HoldToKillButtonState();
}

class _HoldToKillButtonState extends State<HoldToKillButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  bool _isHolding = false;
  bool _hasTriggered = false;

  @override
  void initState() {
    super.initState();
    // ২ সেকেন্ডের ট্রানজিশন (ওয়েবের CSS 'width 2s linear' এর সমতুল্য)
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );

    _controller.addStatusListener((status) {
      if (status == AnimationStatus.completed && !_hasTriggered) {
        _hasTriggered = true;
        widget.onTrigger();
        setState(() {
          _isHolding = false;
        });
        _controller.reset();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _handlePointerDown(_) {
    setState(() {
      _isHolding = true;
      _hasTriggered = false;
    });
    _controller.forward();
  }

  void _handlePointerUp(_) {
    if (!_hasTriggered) {
      setState(() {
        _isHolding = false;
      });
      // বাটন ছেড়ে দিলে দ্রুত আগের অবস্থায় ফিরে যাবে
      _controller.reverse();
    }
  }

  @override
  Widget build(BuildContext context) {
    // Note: Use the exact generated property names from your DesignTokens
    final dangerColor = DesignTokens.brandDangerDark;

    return Listener(
      onPointerDown: _handlePointerDown,
      onPointerUp: _handlePointerUp,
      onPointerCancel: _handlePointerUp,
      child: Container(
        height: 56,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(DesignTokens.radiusMd),
          border: Border.all(color: dangerColor, width: 2),
          boxShadow: [
            BoxShadow(
              color: dangerColor.withOpacity(0.3),
              blurRadius: 15,
              spreadRadius: 2,
            ),
          ],
        ),
        child: Stack(
          children: [
            // Progress Fill Layer
            AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                return FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: _controller.value,
                  child: Container(
                    decoration: BoxDecoration(
                      color: dangerColor.withOpacity(0.8),
                      borderRadius: BorderRadius.circular(DesignTokens.radiusMd - 2),
                    ),
                  ),
                );
              },
            ),
            // Text Layer
            Center(
              child: Text(
                _isHolding ? 'HOLDING TO KILL...' : 'HOLD TO HALT SWARM',
                style: TextStyle(
                  fontFamily: DesignTokens.fontFamilyDisplay, // e.g., 'Outfit'
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  letterSpacing: 1.2,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
