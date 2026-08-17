import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/dashboard_provider.dart';
import '../providers/orchestration_provider.dart';
import '../providers/auth_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/action_hub_card.dart';
import '../widgets/agent_metrics_card.dart';
import '../widgets/live_execution_logger.dart';
import '../widgets/shimmer_loading.dart';
import '../widgets/fade_in_slide.dart';
import '../widgets/supreme_ui/supreme_card.dart';
import '../widgets/supreme_ui/supreme_header.dart';
import '../theme/tokens.dart';
import 'terminal_view.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();

    // 🔥 safe প্র্যাকটিস: ফ্রেম রেন্ডারিং শেষ হওয়ার পর প্রোভাইডার থেকে ডেটা রিড করা হবে
    WidgetsBinding.instance.addPostFrameCallback((_) {
      try {
        context.read<DashboardProvider>().syncDashboard();

        // ১. AuthProvider থেকে রিয়েল টোকেন ফেচ করা হচ্ছে
        final authToken = context.read<AuthProvider>().token ?? '';

        // ২. DashboardProvider থেকে ডাইনামিক অ্যাক্টিভ টাস্ক আইডি ফেচ করা হচ্ছে
        final activeTaskId = context.read<DashboardProvider>().activeTaskId ?? '';

        // ৩. ভ্যালিডেশন চেক: টোকেন বা টাস্ক আইডি মিসিং থাকলে স্ট্রিম রান করবে না
        if (authToken.isNotEmpty && activeTaskId.isNotEmpty) {
          context.read<OrchestrationProvider>().initRealTimeTaskStream(activeTaskId, authToken);
          debugPrint('🚀 [Flutter Dashboard] Live SSE Stream connected for Task: $activeTaskId');
        } else {
          debugPrint('⚠️ [Flutter Dashboard] Stream skipped: Missing Token ($authToken) or Task ID ($activeTaskId)');
        }

        // 4. Start Theme Sync SSE stream
        context.read<SettingsProvider>().listenToThemeSyncStream('default');
      } catch (error) {
        debugPrint('🔴 [Flutter Dashboard] Failed to initialize real-time stream: $error');
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<DashboardProvider>();

    return Scaffold(
      backgroundColor: DesignTokens.colorBgVoidDark,
      appBar: AppBar(
        backgroundColor: DesignTokens.colorBgElevatedDark,
        title: const Text(
          'Supreme Command Center',
          style: TextStyle(fontWeight: FontWeight.bold, color: DesignTokens.colorTextPrimaryDark),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.blueAccent),
            onPressed: () => provider.syncDashboard(),
          )
        ],
      ),
      body: provider.isLoading && provider.jobs.isEmpty
          ? _buildShimmerLoading()
          : RefreshIndicator(
              onRefresh: () => provider.syncDashboard(),
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 🤖 Live Agent Metrics Section
                    const FadeInSlide(
                      delay: Duration(milliseconds: 100),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SupremeHeader(title: '🤖 Live Agent Metrics', gradient: true),
                          SizedBox(height: 12),
                          AgentMetricsCard(),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),

                    const FadeInSlide(
                      delay: Duration(milliseconds: 200),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SupremeHeader(title: '📜 Execution Logs'),
                          SizedBox(height: 8),
                          SupremeCard(
                            padding: EdgeInsets.all(0),
                            child: LiveExecutionLogger(),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    // 🛡️ God Control Section
                    FadeInSlide(
                      delay: const Duration(milliseconds: 300),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SupremeHeader(title: '🛡️ God Control'),
                          const SizedBox(height: 12),
                          SupremeCard(
                            padding: const EdgeInsets.all(8),
                            child: SwitchListTile(
                              title: const Text('Admin Authorized', style: TextStyle(color: DesignTokens.colorDangerDark, fontWeight: FontWeight.bold)),
                              subtitle: const Text('Allow critical write actions globally.', style: TextStyle(color: DesignTokens.colorTextSecondaryDark, fontSize: 12)),
                              value: provider.isAdminAuthorized,
                              activeThumbColor: Colors.redAccent, // বাংলা মন্তব্য: Flutter ৩.২৯.০ সংস্করণে activeThumbColor সাপোর্ট করে না, তাই activeColor ব্যবহার করা হলো।
                              onChanged: (bool value) {
                                provider.toggleGodMode(value);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(content: Text(value ? 'System Unlocked' : 'Read-Only Mode Enforced')),
                                );
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    // ⚡ Quick Actions Section
                    FadeInSlide(
                      delay: const Duration(milliseconds: 400),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SupremeHeader(title: '⚡ Quick Actions'),
                          const SizedBox(height: 12),
                          GridView.count(
                            crossAxisCount: 2,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 12,
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            childAspectRatio: 1.1,
                            children: [
                              ActionHubCard(
                                title: 'Rollback',
                                subtitle: 'Revert Cloud Run',
                                icon: Icons.restore,
                                onTap: () => provider.executeQuickAction('rollback'),
                              ),
                              ActionHubCard(
                                title: 'Clear Cache',
                                subtitle: 'Flush Redis memory',
                                icon: Icons.cleaning_services,
                                onTap: () => provider.executeQuickAction('cache'),
                              ),
                              ActionHubCard(
                                title: 'Deploy',
                                subtitle: 'Cloud Deployment',
                                icon: Icons.cloud_upload,
                                onTap: () => provider.executeQuickAction('deploy'),
                              ),
                              ActionHubCard(
                                title: 'Monitor',
                                subtitle: 'System Health',
                                icon: Icons.monitor_heart,
                                onTap: () => provider.executeQuickAction('monitor'),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    FadeInSlide(
                      delay: const Duration(milliseconds: 500),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SupremeHeader(title: '🚀 CI/CD Pipelines'),
                          const SizedBox(height: 12),
                          ListView.separated(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: provider.jobs.length,
                            separatorBuilder: (context, index) => const SizedBox(height: 8),
                            itemBuilder: (context, index) {
                              final job = provider.jobs[index];
                              final isSuccess = job.status == 'success';
                              final isRunning = job.status == 'running';
                              final isPending = job.status == 'pending';

                              return ListTile(
                                tileColor: DesignTokens.colorBgElevatedDark,
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: const BorderSide(color: DesignTokens.colorBorderAccentDark)),
                                leading: Container(
                                  width: 32,
                                  height: 32,
                                  decoration: BoxDecoration(
                                    color: isSuccess ? DesignTokens.colorSuccessDark.withOpacity(0.2) :
                                           isRunning ? DesignTokens.colorWarningDark.withOpacity(0.2) :
                                           isPending ? DesignTokens.colorInfoDark.withOpacity(0.2) :
                                           DesignTokens.colorDangerDark.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                  child: Icon(
                                    isSuccess ? Icons.check_circle :
                                    isRunning ? Icons.hourglass_empty :
                                    isPending ? Icons.access_time :
                                    Icons.error,
                                    color: isSuccess ? DesignTokens.colorSuccessDark :
                                          isRunning ? DesignTokens.colorWarningDark :
                                          isPending ? DesignTokens.colorInfoDark :
                                          DesignTokens.colorDangerDark,
                                    size: 20,
                                  ),
                                ),
                                title: Text(job.name, style: const TextStyle(color: DesignTokens.colorTextPrimaryDark, fontSize: 14)),
                                subtitle: Text('Status: ${job.status.toUpperCase()}', style: const TextStyle(color: DesignTokens.colorTextSecondaryDark, fontSize: 12)),
                                trailing: isRunning ?
                                  const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation<Color>(Colors.blueAccent)),
                                  ) :
                                  const Icon(Icons.chevron_right, color: DesignTokens.colorTextSecondaryDark),
                                onTap: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (context) => TerminalView(jobId: job.id, status: job.status),
                                    ),
                                  );
                                },
                              );
                            },
                          ),
                        ],
                      ),
                    ),

                    // System Health Section
                    const SizedBox(height: 24),
                    FadeInSlide(
                      delay: const Duration(milliseconds: 600),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const SupremeHeader(title: '📊 System Health'),
                          const SizedBox(height: 12),
                          SupremeCard(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              children: [
                                _buildHealthMetric('CPU Usage', '24%', 24, Colors.green),
                                const SizedBox(height: 12),
                                _buildHealthMetric('Memory Usage', '45%', 45, Colors.amber),
                                const SizedBox(height: 12),
                                _buildHealthMetric('Disk Usage', '62%', 62, Colors.orange),
                                const SizedBox(height: 12),
                                _buildHealthMetric('Network', '12Mbps', 12, Colors.blue),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildHealthMetric(String title, String value, int percentage, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(title, style: const TextStyle(color: DesignTokens.colorTextSecondaryDark, fontSize: 12)),
            Text(value, style: const TextStyle(color: DesignTokens.colorTextPrimaryDark, fontSize: 14, fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 4),
        LinearProgressIndicator(
          value: percentage / 100,
          backgroundColor: DesignTokens.colorBgElevatedDark,
          valueColor: AlwaysStoppedAnimation<Color>(color),
        ),
      ],
    );
  }

  Widget _buildShimmerLoading() {
    return const SingleChildScrollView(
      padding: EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShimmerLoading(width: 150, height: 24),
          SizedBox(height: 12),
          ShimmerLoading(width: double.infinity, height: 120),
          SizedBox(height: 24),

          ShimmerLoading(width: 150, height: 24),
          SizedBox(height: 12),
          ShimmerLoading(width: double.infinity, height: 200),
          SizedBox(height: 24),

          ShimmerLoading(width: 150, height: 24),
          SizedBox(height: 12),
          ShimmerLoading(width: double.infinity, height: 80),
        ],
      ),
    );
  }
}
