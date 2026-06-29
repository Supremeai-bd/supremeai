import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/dashboard_provider.dart';
import '../widgets/action_hub_card.dart';
import 'terminal_view.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DashboardProvider>().syncDashboard();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<DashboardProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF080B12), // Deep Space Dark
      appBar: AppBar(
        backgroundColor: const Color(0xFF111827),
        title: const Text(
          'Supreme Command Center',
          style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.blueAccent),
            onPressed: () => provider.syncDashboard(),
          )
        ],
      ),
      body: provider.isLoading && provider.jobs.isEmpty
          ? const Center(child: CircularProgressIndicator(color: Colors.blueAccent))
          : RefreshIndicator(
              onRefresh: () => provider.syncDashboard(),
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 🛡️ God Control Section
                    const Text('🛡️ God Control', style: TextStyle(color: Colors.redAccent, fontSize: 18, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 12),
                    Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF1F2937),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.redAccent.withOpacity(0.3)),
                      ),
                      child: SwitchListTile(
                        title: const Text('Admin Authorized', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        subtitle: const Text('Allow critical write actions globally.', style: TextStyle(color: Colors.grey, fontSize: 12)),
                        value: provider.isAdminAuthorized,
                        activeColor: Colors.redAccent,
                        onChanged: (bool value) async {
                          await provider.toggleGodMode(value);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(value ? 'System Unlocked' : 'Read-Only Mode Enforced')),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 24),

                    // ⚡ Quick Actions Section
                    const Text('⚡ Quick Actions', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
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
                      ],
                    ),
                    const SizedBox(height: 24),

                    // 🚀 CI/CD Pipelines Section
                    const Text('🚀 CI/CD Pipelines', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 12),
                    ListView.separated(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: provider.jobs.length,
                      separatorBuilder: (context, index) => const SizedBox(height: 8),
                      itemBuilder: (context, index) {
                        final job = provider.jobs[index];
                        final isSuccess = job.status == 'success';
                        
                        return ListTile(
                          tileColor: const Color(0xFF1F2937),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: BorderSide(color: Colors.white.withOpacity(0.05))),
                          leading: Icon(
                            isSuccess ? Icons.check_circle : Icons.error,
                            color: isSuccess ? Colors.greenAccent : Colors.redAccent,
                          ),
                          title: Text(job.name, style: const TextStyle(color: Colors.white, fontSize: 14)),
                          subtitle: Text('Status: ${job.status.toUpperCase()}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                          trailing: const Icon(Icons.chevron_right, color: Colors.grey),
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
            ),
    );
  }
}
