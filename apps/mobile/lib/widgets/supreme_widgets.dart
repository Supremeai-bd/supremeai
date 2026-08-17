import 'package:flutter/material.dart';
import 'supreme_theme.dart';

// ============================================
// SupremeCard
// ============================================
class SupremeCard extends StatelessWidget {
  final Widget child;
  final Color? accentColor;
  final VoidCallback? onTap;
  final bool hoverable;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry margin;

  const SupremeCard({
    super.key,
    required this.child,
    this.accentColor,
    this.onTap,
    this.hoverable = true,
    this.padding = const EdgeInsets.all(SupremeSpacing.xxl),
    this.margin = EdgeInsets.zero,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        color: SupremeColors.surface,
        borderRadius: BorderRadius.circular(SupremeBorderRadius.lg),
        border: Border.all(color: SupremeColors.border),
        boxShadow: hoverable ? SupremeShadows.sm : null,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(SupremeBorderRadius.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Accent line at top
            Container(
              height: 3,
              decoration: BoxDecoration(
                gradient: accentColor != null
                    ? LinearGradient(
                        colors: [accentColor!, SupremeColors.secondary, SupremeColors.tertiary],
                      )
                    : SupremeColors.gradientPrimary,
              ),
            ),
            Padding(
              padding: padding,
              child: child,
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================
// SupremeButton
// ============================================
enum SupremeButtonVariant { primary, secondary, success, danger, ghost }
enum SupremeButtonSize { sm, md, lg }

class SupremeButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final SupremeButtonVariant variant;
  final SupremeButtonSize size;
  final IconData? icon;
  final bool isLoading;
  final bool isDisabled;

  const SupremeButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = SupremeButtonVariant.primary,
    this.size = SupremeButtonSize.md,
    this.icon,
    this.isLoading = false,
    this.isDisabled = false,
  });

  @override
  Widget build(BuildContext context) {
    double paddingV = SupremeSpacing.md;
    double paddingH = SupremeSpacing.xl;
    double fontSize = 14;

    if (size == SupremeButtonSize.sm) {
      paddingV = SupremeSpacing.sm;
      paddingH = SupremeSpacing.lg;
      fontSize = 12;
    } else if (size == SupremeButtonSize.lg) {
      paddingV = SupremeSpacing.lg;
      paddingH = SupremeSpacing.xxxl;
      fontSize = 16;
    }

    Color bgColor = SupremeColors.primary;
    Color textColor = Colors.white;

    if (variant == SupremeButtonVariant.secondary) {
      bgColor = SupremeColors.surfaceHover;
      textColor = SupremeColors.textSecondary;
    } else if (variant == SupremeButtonVariant.success) {
      bgColor = SupremeColors.success;
    } else if (variant == SupremeButtonVariant.danger) {
      bgColor = SupremeColors.danger;
    } else if (variant == SupremeButtonVariant.ghost) {
      bgColor = Colors.transparent;
      textColor = SupremeColors.textSecondary;
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: (isDisabled || isLoading) ? null : onPressed,
        borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
        child: Ink(
          padding: EdgeInsets.symmetric(horizontal: paddingH, vertical: paddingV),
          decoration: BoxDecoration(
            color: isDisabled ? SupremeColors.surfaceDisabled : bgColor,
            borderRadius: BorderRadius.circular(SupremeBorderRadius.md),
            border: variant == SupremeButtonVariant.secondary
                ? Border.all(color: SupremeColors.border)
                : null,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (isLoading) ...[
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                ),
                const SizedBox(width: SupremeSpacing.sm),
              ] else if (icon != null) ...[
                Icon(icon, size: fontSize + 2, color: textColor),
                const SizedBox(width: SupremeSpacing.sm),
              ],
              Text(
                label,
                style: TextStyle(
                  color: textColor,
                  fontSize: fontSize,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================
// SupremeBadge
// ============================================
enum SupremeBadgeVariant { primary, success, warning, danger, info, neutral }

class SupremeBadge extends StatelessWidget {
  final String label;
  final SupremeBadgeVariant variant;
  final bool pulse;

  const SupremeBadge({
    super.key,
    required this.label,
    this.variant = SupremeBadgeVariant.primary,
    this.pulse = false,
  });

  @override
  Widget build(BuildContext context) {
    Color bg = SupremeColors.primary.withOpacity(0.1);
    Color fg = SupremeColors.primaryLight;
    Color border = SupremeColors.primary.withOpacity(0.3);

    if (variant == SupremeBadgeVariant.success) {
      bg = SupremeColors.success.withOpacity(0.1);
      fg = SupremeColors.successLight;
      border = SupremeColors.success.withOpacity(0.3);
    } else if (variant == SupremeBadgeVariant.warning) {
      bg = SupremeColors.warning.withOpacity(0.1);
      fg = SupremeColors.warningLight;
      border = SupremeColors.warning.withOpacity(0.3);
    } else if (variant == SupremeBadgeVariant.danger) {
      bg = SupremeColors.danger.withOpacity(0.1);
      fg = SupremeColors.dangerLight;
      border = SupremeColors.danger.withOpacity(0.3);
    } else if (variant == SupremeBadgeVariant.info) {
      bg = SupremeColors.info.withOpacity(0.1);
      fg = SupremeColors.infoLight;
      border = SupremeColors.info.withOpacity(0.3);
    } else if (variant == SupremeBadgeVariant.neutral) {
      bg = SupremeColors.surfaceHover;
      fg = SupremeColors.textSecondary;
      border = SupremeColors.border;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: SupremeSpacing.md, vertical: SupremeSpacing.xs),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(SupremeBorderRadius.full),
        border: Border.all(color: border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (pulse) ...[
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                color: fg,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: SupremeSpacing.xs),
          ],
          Text(
            label,
            style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
