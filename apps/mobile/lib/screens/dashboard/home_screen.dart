import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../services/localization_service.dart';
import '../../widgets/agent_metrics_card.dart';
import '../../widgets/action_hub_card.dart';
import '../../widgets/ai_assistance_card.dart';
import '../agent_chat_screen.dart';
import '../wallet_screen.dart';
import '../byoc_hub_screen.dart';
import '../projects/projects_list_screen.dart';
import '../notifications/notifications_screen.dart';
import '../analytics/analytics_screen.dart';
import '../api_keys_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    // বাংলা মন্তব্য: ওয়েব ড্যাশবোর্ডের মতো রিচ হোম ওভারভিউ — একাধিক ফিচার কার্ড ও দ্রুত নেভিগেশন
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: Text('SupremeAI'.tr(), style: const TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5, color: Colors.white)),
        actions: [
          IconButton(
            icon: Icon(auth.isGuest ? Icons.login : Icons.logout, color: Colors.white70),
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // বাংলা মন্তব্য: গ্রিটিং হেডার
            Text(
              'Welcome Back!'.tr(),
              style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 6),
            Text(
              'How can SupremeAI assist you today?'.tr(),
              style: const TextStyle(color: Colors.white54, fontSize: 14),
            ),
            const SizedBox(height: 20),

            // বাংলা মন্তব্য: লাইভ এজেন্ট মেট্রিক্স (ওয়েবের Agent Workspace এর সমতুল্য)
            const AgentMetricsCard(),
            const SizedBox(height: 24),

            // বাংলা মন্তব্য: কুইক অ্যাকশন হাব গ্রিড
            Text(
              'Quick Actions'.tr().toUpperCase(),
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54),
            ),
            const SizedBox(height: 12),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.1,
              children: [
                ActionHubCard(
                  title: 'Wallet',
                  subtitle: 'Balance & billing',
                  icon: Icons.account_balance_wallet_outlined,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const WalletScreen())),
                ),
                ActionHubCard(
                  title: 'BYOC Hub',
                  subtitle: 'Bring your own cloud',
                  icon: Icons.cloud_upload_outlined,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ByocHubScreen())),
                ),
                ActionHubCard(
                  title: 'Projects',
                  subtitle: 'Your workspaces',
                  icon: Icons.folder_outlined,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ProjectsListScreen())),
                ),
                ActionHubCard(
                  title: 'Notifications',
                  subtitle: 'Alerts & updates',
                  icon: Icons.notifications_outlined,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const NotificationsScreen())),
                ),
                ActionHubCard(
                  title: 'Analytics',
                  subtitle: 'System health',
                  icon: Icons.analytics_outlined,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AnalyticsScreen())),
                ),
                ActionHubCard(
                  title: 'API Keys',
                  subtitle: 'Manage credentials',
                  icon: Icons.key_outlined,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ApiKeysScreen())),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // বাংলা মন্তব্য: AI অ্যাসিস্ট্যান্স শর্টকাট
            Text(
              'AI Assistance'.tr().toUpperCase(),
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900, letterSpacing: 2, color: Colors.white54),
            ),
            const SizedBox(height: 12),
            AIAssistanceCard(
              title: 'Code Review',
              description: 'Get AI feedback on your code',
              icon: Icons.rule_rounded,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AgentChatScreen())),
            ),
            const SizedBox(height: 12),
            AIAssistanceCard(
              title: 'Bug Fix',
              description: 'Find and fix code issues',
              icon: Icons.bug_report,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AgentChatScreen())),
            ),
            const SizedBox(height: 12),
            AIAssistanceCard(
              title: 'Optimization',
              description: 'Improve code performance',
              icon: Icons.tune,
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AgentChatScreen())),
            ),
            const SizedBox(height: 24),

            // বাংলা মন্তব্য: চ্যাট ওপেন করার সরাসরি বাটন
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blueAccent,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AgentChatScreen())),
                icon: const Icon(Icons.chat_bubble_outline),
                label: Text('Open AI Chat'.tr(), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

}
