import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'package:supremeai/theme/colors.dart'; // SupremeColors ইমপোর্ট ঠিক করা হলো
import '../services/localization_service.dart';

class SupremeBottomNav extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTabTapped;

  const SupremeBottomNav({
    super.key,
    required this.currentIndex,
    required this.onTabTapped,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: SupremeColors.bgSurface,
        border: Border(
          top: BorderSide(
            color: SupremeColors.brandPrimary.withOpacity(0.2),
            width: 1.0,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: SupremeColors.brandPrimary.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, -4),
          )
        ],
      ),
      child: BottomNavigationBar(
        currentIndex: currentIndex,
        onTap: onTabTapped,
        backgroundColor: Colors.transparent,
        elevation: 0,
        type: BottomNavigationBarType.fixed,
        selectedItemColor: SupremeColors.brandPrimary,
        unselectedItemColor: SupremeColors.textMuted.withOpacity(0.5),
        showSelectedLabels: true,
        showUnselectedLabels: true,
        selectedLabelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
        unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.normal, fontSize: 11),
        items: [
          BottomNavigationBarItem(
            icon: const Icon(Icons.home_outlined),
            activeIcon: _buildActiveIcon(Icons.home, true),
            label: 'nav.home'.tr(),
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.analytics_outlined),
            activeIcon: _buildActiveIcon(Icons.analytics, true),
            label: 'nav.analytics'.tr(),
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.chat_bubble_outline),
            activeIcon: _buildActiveIcon(Icons.chat_bubble, true),
            label: 'nav.chat'.tr(),
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.key_outlined),
            activeIcon: _buildActiveIcon(Icons.key, true),
            label: 'nav.api'.tr(),
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.settings_outlined),
            activeIcon: _buildActiveIcon(Icons.settings, true),
            label: 'nav.settings'.tr(),
          ),
        ],
      ),
    );
  }

  Widget _buildActiveIcon(IconData icon, bool isActive) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutBack,
      padding: EdgeInsets.all(isActive ? 6 : 0),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        boxShadow: isActive ? [
          BoxShadow(
            color: SupremeColors.brandPrimary.withOpacity(0.4),
            blurRadius: 12,
            spreadRadius: 2,
          )
        ] : [],
      ),
      child: Icon(icon, color: isActive ? SupremeColors.brandPrimary : SupremeColors.textMuted.withOpacity(0.5)),
    );
  }
}
