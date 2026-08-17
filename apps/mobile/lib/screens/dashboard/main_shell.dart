import 'package:flutter/material.dart';
import '../../widgets/supreme_bottom_nav.dart';
import '../../theme/app_theme.dart';
import 'package:supremeai/theme/colors.dart'; // SupremeColors ইমপোর্ট ঠিক করা হলো
// বাংলা মন্তব্য: প্লেসহোল্ডারের বদলে রিয়েল স্ক্রিন ওয়্যার করা হয়েছে যাতে ওয়েব ড্যাশবোর্ডের মতো ফিচার মোবাইলেও পাওয়া যায়
import 'home_screen.dart'; // dashboard_screen এর বদলে home_screen ব্যবহার করা হলো
import '../analytics/analytics_screen.dart';
import '../agent_chat_screen.dart';
import '../api_keys_screen.dart';
import '../settings_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;
  late PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pageController = PageController(initialPage: _currentIndex);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _onTabTapped(int index) {
    setState(() {
      _currentIndex = index;
    });
    _pageController.jumpToPage(index);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SupremeColors.bgVoid,
      body: PageView(
        controller: _pageController,
        physics: const NeverScrollableScrollPhysics(), // Disable swipe to change tab
        children: const [
          HomeScreen(),
          AnalyticsScreen(),
          AgentChatScreen(),
          ApiKeysScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: SupremeBottomNav(
        currentIndex: _currentIndex,
        onTabTapped: _onTabTapped,
      ),
    );
  }
}
