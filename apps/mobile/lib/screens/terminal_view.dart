import 'package:flutter/material.dart';
import '../services/ci_sync_service.dart';

class TerminalView extends StatefulWidget {
  final String jobId;
  final String status;

  const TerminalView({Key? key, required this.jobId, required this.status}) : super(key: key);

  @override
  _TerminalViewState createState() => _TerminalViewState();
}

class _TerminalViewState extends State<TerminalView> {
  final CiSyncService _syncService = CiSyncService();
  List<String> _logs = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchAndSimulateLogs();
  }

  Future<void> _fetchAndSimulateLogs() async {
    final rawMarkdown = await _syncService.fetchLatestLog();
    final lines = rawMarkdown.split('\n').where((line) => line.trim().isNotEmpty).take(40).toList();
    
    // Simulate real-time typing effect
    for (int i = 0; i < lines.length; i++) {
      await Future.delayed(const Duration(milliseconds: 150));
      if (mounted) {
        setState(() {
          _logs.add("> ${lines[i]}");
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0C0C0C),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E1E1E),
        title: Text(
          'logs/${widget.jobId}.log',
          style: const TextStyle(fontFamily: 'monospace', fontSize: 14, color: Colors.grey),
        ),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: _isLoading && _logs.isEmpty
            ? const Center(child: CircularProgressIndicator(color: Colors.greenAccent))
            : ListView.builder(
                itemCount: _logs.length,
                itemBuilder: (context, index) {
                  final line = _logs[index];
                  final isError = line.toLowerCase().contains('failed') || line.toLowerCase().contains('error');
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text(
                      line,
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: isError ? Colors.redAccent : Colors.greenAccent,
                        fontSize: 13,
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }
}
