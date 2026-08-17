import 'package:flutter/material.dart';
import '../services/byoc_service.dart';
import '../services/deployment_stream.dart';
import '../widgets/json_dropzone.dart';
import '../widgets/live_terminal.dart';

class ByocHubScreen extends StatefulWidget {
  const ByocHubScreen({super.key});

  @override
  State<ByocHubScreen> createState() => _ByocHubScreenState();
}

class _ByocHubScreenState extends State<ByocHubScreen> {
  final ByocService _byocService = ByocService();
  final DeploymentStream _deploymentStream = DeploymentStream();

  Map<String, dynamic>? _tempCredentials;
  bool _isUploading = false;
  bool _isDeploying = false;
  String? _activeJobId;

  // Stream tracking deployment
  Stream<Map<String, dynamic>>? _logsStream;

  // Zero-Trust: Handle files directly in memory (RAM).
  // Device caches are completely bypassed for absolute credential isolation.
  // বাংলা মন্তব্য: জিরো-ট্রাস্ট মেমরি ক্লিনআপ - ক্রেডেনশিয়াল নাল (Null) করে দেওয়া হলো যাতে র‍্যামে মেমোরি লিক না হয়।
  void _onCredentialsLoaded(Map<String, dynamic> credentials) {
    setState(() {
      _tempCredentials = credentials;
    });
  }

  Future<void> _uploadCredentials() async {
    if (_tempCredentials == null) return;
    setState(() {
      _isUploading = true;
    });

    final res = await _byocService.uploadCredentials(_tempCredentials!);

    setState(() {
      _isUploading = false;
      // Zero-Trust: Clear credentials immediately from RAM memory space
      _tempCredentials = null;
    });

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(res['success'] == true ? "Credentials saved successfully." : "Error: ${res['error']}"),
          backgroundColor: res['success'] == true ? Colors.green : Colors.red,
        ),
      );
    }
  }

  Future<void> _deploySkill() async {
    setState(() {
      _isDeploying = true;
      _activeJobId = null;
    });

    final res = await _byocService.deployContainer("supremeai-sandbox");

    if (res['success'] == true) {
      final jobId = res['job_id'];
      setState(() {
        _activeJobId = jobId;
        _logsStream = _deploymentStream.monitorDeployment(jobId);
        _isDeploying = false;
      });
    } else {
      setState(() {
        _isDeploying = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Deployment error: ${res['error']}"),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    _deploymentStream.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text("Universal BYOC Hub"),
        backgroundColor: theme.colorScheme.inversePrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              "Bring Your Own Cloud (BYOC) Dashboard",
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              "Deploy isolated AI skills directly inside your GCP Cloud Run service context securely.",
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),

            // 🛡️ Step 1: Upload Credentials Block
            Card(
              elevation: 0,
              color: theme.colorScheme.surfaceContainerLow,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(color: theme.colorScheme.outlineVariant),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "Step 1: Authenticate Cloud Project",
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    JsonDropzone(onFileLoaded: _onCredentialsLoaded),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      onPressed: _tempCredentials != null && !_isUploading ? _uploadCredentials : null,
                      icon: _isUploading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.vpn_key_outlined),
                      label: Text(_isUploading ? "Encrypting & Saving..." : "Save Secure Credentials"),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // 🚀 Step 2: Container Deployment Block
            Card(
              elevation: 0,
              color: theme.colorScheme.surfaceContainerLow,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(color: theme.colorScheme.outlineVariant),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "Step 2: Deploy Cloud Run Service",
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      "Launch the restricted AI sandbox container inside your private GCP project.",
                      style: theme.textTheme.bodySmall,
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: !_isDeploying ? _deploySkill : null,
                      icon: const Icon(Icons.rocket_launch_outlined),
                      label: const Text("Launch Container Deploy"),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // 📊 Step 3: Isolated Real-time logs terminal (Preventing Jank)
            if (_activeJobId != null && _logsStream != null) ...[
              const SizedBox(height: 24),
              Text(
                "Terraform Live Logs Stream",
                style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),

              // Isolated UI Rebuild Block using StreamBuilder
              // বাংলা মন্তব্য: UI রি-রেন্ডারিং জ্যাঙ্ক এড়াতে স্ট্রিম-বিল্ডার ব্যবহার করে টার্মিনাল লগ আইসোলেট করা হয়েছে।
              StreamBuilder<Map<String, dynamic>>(
                stream: _logsStream,
                builder: (context, snapshot) {
                  if (snapshot.hasError) {
                    return Text("Error loading stream: ${snapshot.error}");
                  }
                  if (!snapshot.hasData) {
                    return const LiveTerminal(logs: ["Waiting for logs stream..."]);
                  }

                  final job = snapshot.data!;
                  final List<dynamic> logsDyn = job['logs'] ?? [];
                  final logs = logsDyn.map((e) => e.toString()).toList();

                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      LiveTerminal(logs: logs),
                      const SizedBox(height: 8),
                      if (job['service_url'] != null)
                        SelectableText(
                          "Service URL: ${job['service_url']}",
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: Colors.green,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                    ],
                  );
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}
