import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class FadeInSlide extends StatefulWidget {
  final Widget child;
  final Duration? duration;
  final Duration delay;
  final Offset slideOffset;

  const FadeInSlide({
    super.key,
    required this.child,
    this.duration,
    this.delay = Duration.zero,
    this.slideOffset = const Offset(0, 0.2), // Starts slightly below
  });

  @override
  State<FadeInSlide> createState() => _FadeInSlideState();
}

class _FadeInSlideState extends State<FadeInSlide> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: widget.duration ?? DesignTokens.motionDurationNormal);

    _fadeAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: DesignTokens.motionEasingStandard),
    );

    _slideAnimation = Tween<Offset>(begin: widget.slideOffset, end: Offset.zero).animate(
      CurvedAnimation(parent: _controller, curve: DesignTokens.motionEasingBounce),
    );

    if (widget.delay == Duration.zero) {
      _controller.forward();
    } else {
      Future.delayed(widget.delay, () {
        if (mounted) _controller.forward();
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeAnimation,
      child: SlideTransition(
        position: _slideAnimation,
        child: widget.child,
      ),
    );
  }
}
